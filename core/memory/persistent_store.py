"""
Persistent local storage for the Elite MCP Server.
Handles ONLY our unique moat: anti-patterns, decisions, quality scores,
benchmarks, goals, smoke tests, and after-action reviews.
Memory/context is delegated to AgentMemory or Mem0.
"""
import contextlib
import json
import os
import sqlite3
import threading
import time

try:
    import struct  # noqa: F401

    import sqlite_vec
except ImportError:
    sqlite_vec = None

import logging

logger = logging.getLogger(__name__)

from core.memory.graph_store import TemporalGraphStore  # noqa: E402


class EliteStore:
    """Local SQLite store for anti-patterns, decisions, quality, benchmarks, goals, and reviews."""

    def __init__(self, brain_dir: str):
        self.brain_dir = brain_dir
        self.db_path = os.path.join(brain_dir, "elite.db")
        self._local = threading.local()
        os.makedirs(brain_dir, exist_ok=True)

        # P1: Use ThreadLocalPool for connection management
        # Falls back to direct connection if pool module unavailable
        try:
            from core.memory.connection_pool import ThreadLocalPool
            self._pool = ThreadLocalPool(self.db_path)
            self._use_pool = True
        except ImportError:
            self._pool = None
            self._use_pool = False

        self._init_db()
        self.graph = TemporalGraphStore(self.db_path)  # Same DB — single transaction boundary

    def _connect(self) -> sqlite3.Connection:
        """Get a connection. Pool-backed: stays alive across calls."""
        if self._use_pool:
            conn = self._pool._get_connection()
            # Load sqlite_vec if available and not yet loaded for this connection
            if sqlite_vec is not None and not getattr(conn, '_vec_loaded', False):
                try:
                    conn.enable_load_extension(True)
                    sqlite_vec.load(conn)
                    conn._vec_loaded = True
                except Exception:
                    pass
            return conn

        # Fallback: original thread-local caching
        cached = getattr(self._local, 'conn', None)
        if cached is not None:
            try:
                cached.execute("SELECT 1")
                return cached
            except Exception:
                self._local.conn = None
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=120000;")
        conn.execute("PRAGMA foreign_keys=ON;")
        if sqlite_vec is not None:
            conn.enable_load_extension(True)
            try:
                sqlite_vec.load(conn)
            except Exception:
                pass
        self._local.conn = conn
        return conn

    def _close(self, conn):
        """Commit pending changes. Pool-backed: connection stays alive."""
        if getattr(self._local, 'in_transaction', False):
            return
        if self._use_pool:
            # Pool connections stay alive — just commit any pending autocommit
            try:
                conn.execute("SELECT 1")  # Verify connection is alive
            except Exception:
                pass
            return
        # Fallback: original close behavior
        conn.commit()
        conn.close()
        self._local.conn = None

    @contextlib.contextmanager
    def transaction(self):
        """Write transaction. Pool-backed: uses BEGIN IMMEDIATE for fail-fast locking."""
        if getattr(self._local, 'in_transaction', False):
            yield
            return

        if self._use_pool:
            # Use pool's transaction context manager
            self._local.in_transaction = True
            # Share connection with graph if same DB
            same_db = (os.path.abspath(self.db_path) == os.path.abspath(self.graph.db_path))
            try:
                with self._pool.transaction() as conn:
                    if same_db:
                        self.graph._local.in_transaction = True
                        self.graph._local.conn = conn
                    yield
            finally:
                self._local.in_transaction = False
                if same_db:
                    self.graph._local.in_transaction = False
                    self.graph._local.conn = None
            return

        # Fallback: original transaction logic
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=120000;")
        conn.execute("PRAGMA foreign_keys=ON;")
        if sqlite_vec is not None:
            conn.enable_load_extension(True)
            try:
                sqlite_vec.load(conn)
            except Exception:
                pass

        conn.isolation_level = None
        self._local.in_transaction = True
        self._local.conn = conn

        same_db = (os.path.abspath(self.db_path) == os.path.abspath(self.graph.db_path))
        if same_db:
            graph_conn = conn
        else:
            graph_conn = sqlite3.connect(self.graph.db_path, check_same_thread=False, timeout=30.0)
            graph_conn.row_factory = sqlite3.Row
            graph_conn.isolation_level = None
        self.graph._local.in_transaction = True
        self.graph._local.conn = graph_conn

        try:
            conn.execute("BEGIN IMMEDIATE")
            if not same_db:
                graph_conn.execute("BEGIN IMMEDIATE")
            yield
            conn.execute("COMMIT")
            if not same_db:
                graph_conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            if not same_db:
                try:
                    graph_conn.execute("ROLLBACK")
                except Exception:
                    pass
            raise
        finally:
            self._local.in_transaction = False
            self._local.conn = None
            self.graph._local.in_transaction = False
            self.graph._local.conn = None
            conn.close()
            if not same_db:
                graph_conn.close()

    def _init_db(self):
        conn = self._connect()
        c = conn.cursor()

        # --- Anti-patterns (mistake immunity) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS anti_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mistake TEXT NOT NULL,
                root_cause TEXT NOT NULL,
                fix TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                tags TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS anti_patterns_fts
            USING fts5(mistake, root_cause, fix, tags, content=anti_patterns, content_rowid=id)
        """)
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS anti_patterns_ai AFTER INSERT ON anti_patterns BEGIN
                INSERT INTO anti_patterns_fts(rowid, mistake, root_cause, fix, tags)
                VALUES (new.id, new.mistake, new.root_cause, new.fix, new.tags);
            END
        """)

        if sqlite_vec is not None:
            try:
                c.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS anti_patterns_vec 
                    USING vec0(
                        id INTEGER PRIMARY KEY,
                        embedding float[384]
                    )
                """)
                c.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS decisions_vec 
                    USING vec0(
                        id INTEGER PRIMARY KEY,
                        embedding float[384]
                    )
                """)
            except Exception:
                pass

        # --- Quality scores ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS quality_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                score INTEGER NOT NULL,
                dimension TEXT DEFAULT 'overall',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)

        # --- Decisions (audit trail) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision TEXT NOT NULL,
                rationale TEXT NOT NULL,
                alternatives_rejected TEXT DEFAULT '',
                context TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS decisions_fts
            USING fts5(decision, rationale, alternatives_rejected, context, content=decisions, content_rowid=id)
        """)
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS decisions_ai AFTER INSERT ON decisions BEGIN
                INSERT INTO decisions_fts(rowid, decision, rationale, alternatives_rejected, context)
                VALUES (new.id, new.decision, new.rationale, new.alternatives_rejected, new.context);
            END
        """)

        # --- Benchmarks (SPC baselines & tracking) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS benchmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT DEFAULT '',
                context TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)

        # --- Goals (OKR tracking) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                objective TEXT NOT NULL,
                key_results TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                progress TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # --- Smoke Tests (before/after checkpoints) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS smoke_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                before_state TEXT NOT NULL,
                after_state TEXT DEFAULT '',
                verdict TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        """)

        # --- After Action Reviews ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS action_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                intended TEXT NOT NULL,
                actual TEXT NOT NULL,
                went_well TEXT DEFAULT '',
                improve TEXT NOT NULL,
                learnings TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)

        # --- Prompt Intelligence (adaptive learning) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS prompt_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                prompt_text TEXT NOT NULL,
                intent_category TEXT NOT NULL DEFAULT 'unknown',
                reasoning_type TEXT NOT NULL DEFAULT 'unknown',
                implicit_expectation TEXT DEFAULT '',
                failure_detected TEXT DEFAULT '',
                tools_used TEXT DEFAULT '[]',
                tools_should_have_used TEXT DEFAULT '',
                resolution_quality INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

        # --- Missed Detections (what system should have caught) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS missed_detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger_prompt_id INTEGER,
                detection_type TEXT NOT NULL,
                what_was_missed TEXT NOT NULL,
                root_cause TEXT NOT NULL,
                prevention_rule TEXT NOT NULL,
                automated INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

        # --- User Thinking Patterns (evolves over time) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_thinking_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_name TEXT NOT NULL UNIQUE,
                evidence_count INTEGER DEFAULT 1,
                example_prompts TEXT DEFAULT '[]',
                system_adaptation TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                last_seen TEXT NOT NULL
            )
        """)

        # --- Tool Usage Log (every tool invocation) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS tool_usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                args_summary TEXT DEFAULT '',
                result_summary TEXT DEFAULT '',
                session_id TEXT DEFAULT '',
                duration_ms INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

        # --- Prevention Rules (automated checks) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS prevention_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_name TEXT NOT NULL UNIQUE,
                trigger_event TEXT NOT NULL,
                check_query TEXT NOT NULL,
                action_on_match TEXT NOT NULL,
                severity TEXT DEFAULT 'P1',
                source_detection_id INTEGER,
                times_triggered INTEGER DEFAULT 0,
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                last_evaluated_at REAL,
                evaluation_count INTEGER DEFAULT 0,
                last_error TEXT,
                last_check_query_ms REAL
            )
        """)

        # --- Injection Events (feedback loop measurement) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS injection_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                prompt_embedding BLOB,
                anti_pattern_ids TEXT NOT NULL,
                injected_at REAL NOT NULL,
                outcome TEXT DEFAULT 'unknown',
                resolved_at REAL,
                recurrence_anti_pattern_id INTEGER
            )
        """)

        # --- Reasoning Traces (thought branching) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS reasoning_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                thought_id TEXT NOT NULL,
                branch_id TEXT NOT NULL DEFAULT 'main',
                parent_thought_id TEXT,
                thought_type TEXT NOT NULL,
                content TEXT NOT NULL,
                confidence REAL,
                status TEXT NOT NULL DEFAULT 'open',
                superseded_by TEXT,
                created_at REAL NOT NULL,
                related_decision_id INTEGER,
                related_anti_pattern_ids TEXT,
                UNIQUE(session_id, thought_id)
            )
        """)

        # --- Reasoning Branches ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS reasoning_branches (
                branch_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                forked_from_thought_id TEXT,
                fork_reason TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                winning_thought_id TEXT,
                created_at REAL NOT NULL,
                closed_at REAL,
                PRIMARY KEY(session_id, branch_id)
            )
        """)

        # --- Calibration Log (P3: confidence vs actual outcomes) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS calibration_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id TEXT NOT NULL,
                claim TEXT NOT NULL,
                confidence REAL NOT NULL,
                domain TEXT DEFAULT 'general',
                outcome TEXT DEFAULT NULL,
                outcome_correct INTEGER DEFAULT NULL,
                resolved_at TEXT DEFAULT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # --- Decision Council (P3: multi-perspective adversarial review) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS decision_council (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id INTEGER,
                decision_text TEXT NOT NULL,
                perspective TEXT NOT NULL,
                critique TEXT NOT NULL,
                risk_flags TEXT DEFAULT '[]',
                recommendation TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                created_at TEXT NOT NULL
            )
        """)

        # --- Cost Log (Opus R2 Q13b: track API/embedding/compute costs) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS cost_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                tool_name TEXT,
                cost_type TEXT NOT NULL,
                provider TEXT DEFAULT 'local',
                units REAL DEFAULT 0,
                estimated_usd REAL DEFAULT 0,
                created_at REAL NOT NULL
            )
        """)

        # --- Trigger Effectiveness (Opus R2 Q4: adaptive trigger learning) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS trigger_effectiveness (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                detection_type TEXT NOT NULL,
                trigger_event TEXT NOT NULL,
                fired_count INTEGER DEFAULT 0,
                quality_improved_count INTEGER DEFAULT 0,
                quality_degraded_count INTEGER DEFAULT 0,
                mistake_prevented_count INTEGER DEFAULT 0,
                last_updated REAL,
                UNIQUE(detection_type, trigger_event)
            )
        """)

        # --- Schema Migrations (Opus R2: track applied migrations) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))
            )
        """)

        # --- Optimization Events (v5: cost/metric self-optimization) ---
        c.execute("""
            CREATE TABLE IF NOT EXISTS optimization_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric TEXT NOT NULL,
                value REAL NOT NULL,
                threshold REAL NOT NULL,
                action_taken TEXT,
                created_at REAL NOT NULL
            )
        """)

        # --- INDEXES (P0 fix: 0 indexes existed across 13 tables) ---
        index_stmts = [
            "CREATE INDEX IF NOT EXISTS idx_anti_patterns_created ON anti_patterns(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_quality_scores_created ON quality_scores(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_quality_scores_dimension ON quality_scores(dimension)",
            "CREATE INDEX IF NOT EXISTS idx_benchmarks_metric ON benchmarks(metric, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status)",
            "CREATE INDEX IF NOT EXISTS idx_goals_status_updated ON goals(status, updated_at)",
            "CREATE INDEX IF NOT EXISTS idx_prompt_sessions_session ON prompt_sessions(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_prompt_sessions_reasoning ON prompt_sessions(reasoning_type)",
            "CREATE INDEX IF NOT EXISTS idx_prompt_sessions_created ON prompt_sessions(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_missed_detections_automated ON missed_detections(automated)",
            "CREATE INDEX IF NOT EXISTS idx_missed_detections_type ON missed_detections(detection_type)",
            "CREATE INDEX IF NOT EXISTS idx_tool_usage_log_created ON tool_usage_log(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_tool_usage_log_tool ON tool_usage_log(tool_name)",
            "CREATE INDEX IF NOT EXISTS idx_prevention_rules_enabled ON prevention_rules(enabled)",
            "CREATE INDEX IF NOT EXISTS idx_prevention_rules_trigger ON prevention_rules(enabled, trigger_event)",
            "CREATE INDEX IF NOT EXISTS idx_calibration_log_prediction ON calibration_log(prediction_id)",
            "CREATE INDEX IF NOT EXISTS idx_calibration_log_domain ON calibration_log(domain, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_calibration_log_unresolved ON calibration_log(outcome_correct) WHERE outcome_correct IS NULL",
            "CREATE INDEX IF NOT EXISTS idx_decision_council_decision ON decision_council(decision_id)",
            "CREATE INDEX IF NOT EXISTS idx_decision_council_created ON decision_council(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_injection_session ON injection_events(session_id, injected_at)",
            "CREATE INDEX IF NOT EXISTS idx_injection_outcome ON injection_events(outcome)",
            "CREATE INDEX IF NOT EXISTS idx_traces_session_branch ON reasoning_traces(session_id, branch_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_traces_parent ON reasoning_traces(parent_thought_id)",
            "CREATE INDEX IF NOT EXISTS idx_traces_status ON reasoning_traces(session_id, status)",
            # Round 2 indexes
            "CREATE INDEX IF NOT EXISTS idx_cost_log_session ON cost_log(session_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_cost_log_type ON cost_log(cost_type, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_trigger_eff_type ON trigger_effectiveness(detection_type, trigger_event)",
            "CREATE INDEX IF NOT EXISTS idx_anti_patterns_trust ON anti_patterns(trust_score) WHERE quarantined = 0",
            "CREATE INDEX IF NOT EXISTS idx_anti_patterns_quarantine ON anti_patterns(quarantined) WHERE quarantined = 1",
            "CREATE INDEX IF NOT EXISTS idx_rules_lifecycle ON prevention_rules(lifecycle_state)",
            "CREATE INDEX IF NOT EXISTS idx_optimization_metric ON optimization_events(metric, created_at)",
        ]
        for stmt in index_stmts:
            try:
                c.execute(stmt)
            except Exception:
                pass  # Some indexes may reference columns not yet added

        # --- Round 2 ALTER TABLE migrations (idempotent) ---
        # Opus R2 Q13c: Adversarial input handling on anti_patterns
        r2_alterations = [
            "ALTER TABLE anti_patterns ADD COLUMN source TEXT DEFAULT 'llm'",
            "ALTER TABLE anti_patterns ADD COLUMN trust_score REAL DEFAULT 0.5",
            "ALTER TABLE anti_patterns ADD COLUMN quarantined INTEGER DEFAULT 0",
            "ALTER TABLE anti_patterns ADD COLUMN injection_eligible INTEGER DEFAULT 1",
            "ALTER TABLE anti_patterns ADD COLUMN injection_disabled_reason TEXT",
            "ALTER TABLE anti_patterns ADD COLUMN injection_effectiveness REAL",
            # Opus R2 Q10: Temporal confidence on reasoning_traces
            "ALTER TABLE reasoning_traces ADD COLUMN confidence_initial REAL",
            "ALTER TABLE reasoning_traces ADD COLUMN confidence_half_life_days REAL",
            "ALTER TABLE reasoning_traces ADD COLUMN reinforced_at REAL",
            "ALTER TABLE reasoning_traces ADD COLUMN reinforcement_count INTEGER DEFAULT 0",
            # Opus R2 Q6: Rule lifecycle on prevention_rules
            "ALTER TABLE prevention_rules ADD COLUMN lifecycle_state TEXT DEFAULT 'probation'",
            "ALTER TABLE prevention_rules ADD COLUMN promoted_at REAL",
            "ALTER TABLE prevention_rules ADD COLUMN retired_at REAL",
            "ALTER TABLE prevention_rules ADD COLUMN false_positive_count INTEGER DEFAULT 0",
            "ALTER TABLE prevention_rules ADD COLUMN true_positive_count INTEGER DEFAULT 0",
            "ALTER TABLE prevention_rules ADD COLUMN last_triggered_at REAL",
        ]
        for alt in r2_alterations:
            try:
                c.execute(alt)
            except Exception:
                pass  # Column already exists

        # --- One-time trigger migration (Opus R2 Challenge 2) ---
        self._run_trigger_migration(c)

        # --- Learning subsystem migration (v5) ---
        self._run_learning_migration(c)

        self._close(conn)

    def _run_trigger_migration(self, cursor):
        """One-time migration: old trigger vocabulary → canonical.
        After this runs, TRIGGER_MIGRATION map in prevention.py is dead code."""
        try:
            cursor.execute("SELECT version FROM schema_migrations WHERE version = 4")
            if cursor.fetchone():
                return  # Already migrated
        except Exception:
            return  # schema_migrations table doesn't exist yet

        TRIGGER_MAP = {
            "on_prompt": "prompt.received",
            "prompt_received": "prompt.received",
            "on_startup": "session.start",
            "after_tool_call": "tool.after:*",
            "before_design": "phase.before:design",
            "before_code_change": "phase.before:code_change",
            "after_code_change": "phase.after:code_change",
            "pre_commit": "phase.before:commit",
            "after_audit": "phase.after:audit",
        }
        migrated = 0
        for old, new in TRIGGER_MAP.items():
            try:
                result = cursor.execute(
                    "UPDATE prevention_rules SET trigger_event = ? WHERE trigger_event = ?",
                    (new, old)
                )
                migrated += result.rowcount
            except Exception:
                pass
        try:
            cursor.execute("INSERT INTO schema_migrations (version) VALUES (4)")
        except Exception:
            pass
    # ==================== SCHEMA MIGRATION v5: Learning Subsystem ====================

    def _run_learning_migration(self, cursor):
        """Migration v5: Add optimization_events table and injection eligibility columns."""
        try:
            cursor.execute("SELECT version FROM schema_migrations WHERE version = 5")
            if cursor.fetchone():
                return  # Already migrated
        except Exception:
            return

        # Add injection eligibility columns to anti_patterns
        alter_stmts = [
            "ALTER TABLE anti_patterns ADD COLUMN injection_eligible INTEGER DEFAULT 1",
            "ALTER TABLE anti_patterns ADD COLUMN injection_disabled_reason TEXT",
            "ALTER TABLE anti_patterns ADD COLUMN injection_effectiveness REAL",
        ]
        for stmt in alter_stmts:
            try:
                cursor.execute(stmt)
            except Exception:
                pass  # Column may already exist

        # Create optimization_events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS optimization_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric TEXT NOT NULL,
                value REAL NOT NULL,
                threshold REAL NOT NULL,
                action_taken TEXT,
                created_at REAL NOT NULL
            )
        """)

        # Add index for optimization events
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_optimization_metric "
            "ON optimization_events(metric, created_at)"
        )

        try:
            cursor.execute("INSERT INTO schema_migrations (version) VALUES (5)")
        except Exception:
            pass

    # ==================== FTS5 SAFETY ====================

    @staticmethod
    def _sanitize_fts_query(query: str) -> str:
        """Gap #14 fix: Sanitize FTS5 query input to prevent parse errors.
        Strips special FTS5 operators and wraps remaining tokens in quotes."""
        import re
        # Remove FTS5 special characters and operators
        cleaned = re.sub(r'[*()[\]{}^~]', ' ', query)
        # Remove FTS5 boolean operators when used as operators (not inside words)
        cleaned = re.sub(r'\b(AND|OR|NOT|NEAR)\b', ' ', cleaned, flags=re.IGNORECASE)
        # Remove unbalanced quotes
        cleaned = cleaned.replace('"', ' ')
        # Collapse whitespace and strip
        tokens = cleaned.split()
        if not tokens:
            return '""'  # Empty query that matches nothing
        # Wrap each token in quotes to treat as literal
        return ' '.join(f'"{t}"' for t in tokens if t)

    # ==================== ANTI-PATTERNS ====================

    def _get_embedding(self, text: str) -> list[float] | None:
        try:
            import os

            from core.memory.embedding import get_embedding
            os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
            return get_embedding(text)
        except Exception:
            return None

    def record_mistake(self, mistake: str, root_cause: str, fix: str, severity: str = "medium", tags: str = "") -> int:
        # ChatGPT §10 fix: wrap multi-table write in transaction to prevent partial writes
        with self.transaction():
            conn = self._connect()
            c = conn.cursor()

            # Compute embedding ONCE and reuse (Gap #8 fix: was called twice)
            emb = None
            if sqlite_vec is not None:
                emb = self._get_embedding(f"{mistake} {root_cause} {fix}")

            # Dedup: check embedding similarity before inserting
            if emb is not None:
                try:
                    c.execute("""
                        SELECT a.id, v.distance
                        FROM anti_patterns_vec v 
                        JOIN anti_patterns a ON v.id = a.id
                        WHERE v.embedding MATCH ? AND k = 1
                        ORDER BY v.distance
                    """, (sqlite_vec.serialize_float32(emb),))
                    row = c.fetchone()
                    if row and row[1] < 0.15:  # cosine distance < 0.15 means >85% similar
                        return row[0]  # Return existing ID — dedup
                except Exception:
                    pass

            c.execute(
                "INSERT INTO anti_patterns (mistake, root_cause, fix, severity, tags, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (mistake, root_cause, fix, severity, tags, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
            )
            row_id = c.lastrowid

            # Reuse the SAME embedding for vector insert (no second call)
            if emb is not None:
                try:
                    c.execute(
                        "INSERT INTO anti_patterns_vec(id, embedding) VALUES (?, ?)",
                        (row_id, sqlite_vec.serialize_float32(emb))
                    )
                except Exception:
                    pass

            # Extract graph node (inside same transaction boundary)
            self.graph.add_node(
                label="AntiPattern",
                properties={
                    "mistake": mistake,
                    "root_cause": root_cause,
                    "severity": severity,
                    "row_id": row_id
                },
                node_id=f"ap_{row_id}"
            )

        return row_id

    def check_anti_patterns(self, query: str, limit: int = 5) -> list[dict]:
        """Search anti-patterns using HybridSearch (RRF fusion of FTS5 + vec)."""
        try:
            from core.memory.hybrid_search import HybridSearch
            hs = HybridSearch(self, "anti_patterns")
            results = hs.search(query, limit=limit)
            if results:
                return [r.payload for r in results]
        except Exception as e:
            logger.debug(f"HybridSearch fallback for anti_patterns: {e}")

        # Fallback: inline FTS-only search
        conn = self._connect()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT a.id, a.mistake, a.root_cause, a.fix, a.severity, a.tags, a.created_at
                FROM anti_patterns_fts f JOIN anti_patterns a ON f.rowid = a.id
                WHERE anti_patterns_fts MATCH ? ORDER BY rank LIMIT ?
            """, (self._sanitize_fts_query(query), limit))
            return [{"id": r[0], "mistake": r[1], "root_cause": r[2], "fix": r[3],
                     "severity": r[4], "tags": r[5], "created_at": r[6]} for r in c.fetchall()]
        except Exception:
            return []
        finally:
            if not getattr(self._local, 'in_transaction', False):
                self._close(conn)

    def get_all_anti_patterns(self, since: str = None, limit: int = 200) -> list[dict]:
        conn = self._connect()
        c = conn.cursor()
        if since:
            c.execute("SELECT id, mistake, root_cause, fix, severity, tags, created_at FROM anti_patterns WHERE created_at > ? ORDER BY created_at DESC LIMIT ?", (since, limit))
        else:
            c.execute("SELECT id, mistake, root_cause, fix, severity, tags, created_at FROM anti_patterns ORDER BY created_at DESC LIMIT ?", (limit,))
        results = [{"id": r[0], "mistake": r[1], "root_cause": r[2], "fix": r[3],
                     "severity": r[4], "tags": r[5], "created_at": r[6]} for r in c.fetchall()]
        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)
        return results

    def count_anti_patterns(self) -> int:
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM anti_patterns")
        count = c.fetchone()[0]
        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)
        return count

    # ==================== DECISIONS ====================

    def record_decision(self, decision: str, rationale: str, alternatives_rejected: str = "", context: str = "") -> int:
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO decisions (decision, rationale, alternatives_rejected, context, created_at) VALUES (?, ?, ?, ?, ?)",
            (decision, rationale, alternatives_rejected, context, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
        )
        row_id = c.lastrowid

        # Embed the decision for vector search
        if sqlite_vec is not None:
            emb = self._get_embedding(f"{decision} {rationale} {context}")
            if emb:
                try:
                    c.execute(
                        "INSERT INTO decisions_vec(id, embedding) VALUES (?, ?)",
                        (row_id, sqlite_vec.serialize_float32(emb))
                    )
                except Exception:
                    pass

        self._close(conn)

        # Extract graph node
        self.graph.add_node(
            label="Decision",
            properties={
                "decision": decision,
                "rationale": rationale,
                "context": context,
                "row_id": row_id
            },
            node_id=f"dec_{row_id}"
        )

        return row_id

    def search_decisions(self, query: str, limit: int = 10) -> list[dict]:
        """Search decisions using HybridSearch (RRF fusion of FTS5 + vec)."""
        try:
            from core.memory.hybrid_search import HybridSearch
            hs = HybridSearch(self, "decisions")
            results = hs.search(query, limit=limit)
            if results:
                return [r.payload for r in results]
        except Exception as e:
            logger.debug(f"HybridSearch fallback for decisions: {e}")

        # Fallback: inline FTS-only search
        conn = self._connect()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT d.id, d.decision, d.rationale, d.alternatives_rejected, d.context, d.created_at
                FROM decisions_fts f JOIN decisions d ON f.rowid = d.id
                WHERE decisions_fts MATCH ? ORDER BY rank LIMIT ?
            """, (self._sanitize_fts_query(query), limit))
            return [{"id": r[0], "decision": r[1], "rationale": r[2],
                     "alternatives_rejected": r[3], "context": r[4], "created_at": r[5]} for r in c.fetchall()]
        except Exception:
            return []
        finally:
            if not getattr(self._local, 'in_transaction', False):
                self._close(conn)

    def get_all_decisions(self, since: str = None, limit: int = 200) -> list[dict]:
        conn = self._connect()
        c = conn.cursor()
        if since:
            c.execute("SELECT id, decision, rationale, alternatives_rejected, context, created_at FROM decisions WHERE created_at > ? ORDER BY created_at DESC LIMIT ?", (since, limit))
        else:
            c.execute("SELECT id, decision, rationale, alternatives_rejected, context, created_at FROM decisions ORDER BY created_at DESC LIMIT ?", (limit,))
        results = [{"id": r[0], "decision": r[1], "rationale": r[2],
                     "alternatives_rejected": r[3], "context": r[4], "created_at": r[5]} for r in c.fetchall()]
        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)
        return results

    # ==================== QUALITY SCORES ====================

    def record_quality_score(self, score: int, dimension: str = "overall", notes: str = "") -> int:
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO quality_scores (score, dimension, notes, created_at) VALUES (?, ?, ?, ?)",
            (score, dimension, notes, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
        )
        row_id = c.lastrowid
        self._close(conn)
        return row_id

    def get_quality_trend(self, limit: int = 20) -> dict:
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT score, dimension, notes, created_at FROM quality_scores ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)
        if not rows:
            return {"average": 0, "trend": "no_data", "scores": []}
        scores = [r[0] for r in rows]
        avg = sum(scores) / len(scores)
        if len(scores) >= 4:
            mid = len(scores) // 2
            recent = sum(scores[:mid]) / mid
            older = sum(scores[mid:]) / (len(scores) - mid)
            trend = "improving" if recent > older else "declining" if recent < older else "stable"
        else:
            trend = "insufficient_data"
        return {
            "average": round(avg, 1), "trend": trend, "latest": scores[0] if scores else 0,
            "count": len(scores),
            "scores": [{"score": r[0], "dimension": r[1], "notes": r[2], "date": r[3]} for r in rows]
        }

    # ==================== BENCHMARKS (SPC) ====================

    def record_benchmark(self, metric: str, value: float, unit: str = "", context: str = "") -> int:
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO benchmarks (metric, value, unit, context, created_at) VALUES (?, ?, ?, ?, ?)",
            (metric, value, unit, context, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
        )
        row_id = c.lastrowid
        self._close(conn)
        return row_id

    def get_benchmark_trend(self, metric: str, limit: int = 30) -> dict:
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "SELECT value, unit, context, created_at FROM benchmarks WHERE metric = ? ORDER BY created_at DESC LIMIT ?",
            (metric, limit)
        )
        rows = c.fetchall()
        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)
        if not rows:
            return {"metric": metric, "status": "no_data", "values": []}
        values = [r[0] for r in rows]
        avg = sum(values) / len(values)
        import statistics
        stdev = statistics.stdev(values) if len(values) >= 2 else 0
        ucl = avg + 2 * stdev  # Upper control limit (2-sigma)
        lcl = avg - 2 * stdev  # Lower control limit (2-sigma)
        latest = values[0]
        if latest > ucl:
            status = "above_control_limit"
        elif latest < lcl:
            status = "below_control_limit"
        else:
            status = "in_control"
        baseline = values[-1] if values else 0
        delta_pct = ((latest - baseline) / baseline * 100) if baseline != 0 else 0
        return {
            "metric": metric, "latest": latest, "baseline": baseline,
            "average": round(avg, 2), "stdev": round(stdev, 2),
            "ucl": round(ucl, 2), "lcl": round(lcl, 2),
            "delta_pct": round(delta_pct, 1), "status": status, "count": len(values),
            "unit": rows[0][1],
            "values": [{"value": r[0], "context": r[2], "date": r[3]} for r in rows]
        }

    def list_benchmark_metrics(self) -> list[str]:
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT DISTINCT metric FROM benchmarks ORDER BY metric")
        metrics = [r[0] for r in c.fetchall()]
        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)
        return metrics

    # ==================== GOALS (OKR) ====================

    def set_goal(self, objective: str, key_results: list[str]) -> int:
        conn = self._connect()
        c = conn.cursor()
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        progress = {kr: 0 for kr in key_results}
        # Dedup: check if an active goal with the same objective already exists
        c.execute("SELECT id FROM goals WHERE status = 'active' AND objective = ?", (objective,))
        existing = c.fetchone()
        if existing:
            if not getattr(self._local, 'in_transaction', False):
                self._close(conn)
            return existing[0]  # Return existing goal ID instead of creating duplicate
        c.execute(
            "INSERT INTO goals (objective, key_results, status, progress, created_at, updated_at) VALUES (?, ?, 'active', ?, ?, ?)",
            (objective, json.dumps(key_results), json.dumps(progress), now, now)
        )
        row_id = c.lastrowid
        self._close(conn)
        return row_id

    def archive_goal(self, goal_id: int) -> bool:
        conn = self._connect()
        c = conn.cursor()
        c.execute("UPDATE goals SET status = 'archived', updated_at = ? WHERE id = ?",
                  (time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), goal_id))
        changed = c.rowcount > 0
        self._close(conn)
        return changed

    def delete_goal(self, goal_id: int) -> bool:
        conn = self._connect()
        c = conn.cursor()
        c.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
        changed = c.rowcount > 0
        self._close(conn)
        return changed

    def update_goal_progress(self, goal_id: int, key_result: str, progress: int) -> bool:
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT progress, key_results FROM goals WHERE id = ?", (goal_id,))
        row = c.fetchone()
        if not row:
            if not getattr(self._local, 'in_transaction', False):
                self._close(conn)
            return False
        prog = json.loads(row[0])
        prog[key_result] = min(progress, 100)
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        c.execute("UPDATE goals SET progress = ?, updated_at = ? WHERE id = ?", (json.dumps(prog), now, goal_id))
        self._close(conn)
        return True

    def get_active_goals(self) -> list[dict]:
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT id, objective, key_results, status, progress, created_at, updated_at FROM goals WHERE status = 'active' ORDER BY created_at DESC")
        results = []
        for r in c.fetchall():
            kr = json.loads(r[2])
            prog = json.loads(r[4])
            overall = sum(prog.values()) / len(prog) if prog else 0
            results.append({
                "id": r[0], "objective": r[1], "key_results": kr, "status": r[3],
                "progress": prog, "overall_pct": round(overall, 1),
                "created_at": r[5], "updated_at": r[6]
            })
        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)
        return results

    def complete_goal(self, goal_id: int) -> bool:
        conn = self._connect()
        c = conn.cursor()
        c.execute("UPDATE goals SET status = 'completed', updated_at = ? WHERE id = ?",
                  (time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), goal_id))
        changed = c.rowcount > 0
        self._close(conn)
        return changed

    def get_goals(self) -> list[dict]:
        """Gap #10 fix: Alias for get_active_goals that returns key_results as
        list of dicts with 'description' and 'progress' keys, matching what
        _auto_update_goals expects in auditing.py."""
        active = self.get_active_goals()
        for g in active:
            progress = g.get("progress", {})
            kr_list = g.get("key_results", [])
            g["key_results"] = [
                {"description": kr, "progress": progress.get(kr, 0)}
                for kr in kr_list
            ]
        return active

    def update_goal(self, goal_id: int, key_result: str, progress: int) -> bool:
        """Alias for update_goal_progress (used by _auto_update_goals)."""
        return self.update_goal_progress(goal_id, key_result, progress)

    # ==================== SMOKE TESTS ====================

    def create_smoke_test(self, description: str, before_state: str) -> int:
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO smoke_tests (description, before_state, created_at) VALUES (?, ?, ?)",
            (description, before_state, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
        )
        row_id = c.lastrowid
        self._close(conn)
        return row_id

    def complete_smoke_test(self, test_id: int, after_state: str, verdict: str) -> bool:
        conn = self._connect()
        c = conn.cursor()
        c.execute("UPDATE smoke_tests SET after_state = ?, verdict = ? WHERE id = ?", (after_state, verdict, test_id))
        changed = c.rowcount > 0
        self._close(conn)
        return changed

    def get_smoke_test(self, test_id: int) -> dict | None:
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT id, description, before_state, after_state, verdict, created_at FROM smoke_tests WHERE id = ?", (test_id,))
        r = c.fetchone()
        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)
        if not r:
            return None
        return {"id": r[0], "description": r[1], "before_state": r[2], "after_state": r[3], "verdict": r[4], "created_at": r[5]}

    # ==================== AFTER ACTION REVIEWS ====================

    def record_aar(self, intended: str, actual: str, went_well: str, improve: str, learnings: str = "") -> int:
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO action_reviews (intended, actual, went_well, improve, learnings, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (intended, actual, went_well, improve, learnings, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
        )
        row_id = c.lastrowid
        self._close(conn)
        return row_id

    def get_recent_aars(self, limit: int = 10) -> list[dict]:
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT id, intended, actual, went_well, improve, learnings, created_at FROM action_reviews ORDER BY created_at DESC LIMIT ?", (limit,))
        results = [{"id": r[0], "intended": r[1], "actual": r[2], "went_well": r[3],
                     "improve": r[4], "learnings": r[5], "created_at": r[6]} for r in c.fetchall()]
        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)
        return results

    # ==================== PROMPT INTELLIGENCE ====================

    def record_prompt_intent(self, session_id: str, prompt_text: str,
                             intent_category: str = 'unknown',
                             reasoning_type: str = 'unknown',
                             implicit_expectation: str = '',
                             failure_detected: str = '') -> int:
        """Record a user prompt with extracted intent and reasoning."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            """INSERT INTO prompt_sessions 
               (session_id, prompt_text, intent_category, reasoning_type,
                implicit_expectation, failure_detected, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, prompt_text, intent_category, reasoning_type,
             implicit_expectation, failure_detected, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
        )
        row_id = c.lastrowid
        self._close(conn)
        return row_id

    def analyze_prompt_sequence(self, session_id: str = '', limit: int = 20) -> dict:
        """Analyze the last N prompts to detect meta-patterns.
        Returns pattern analysis with escalation, repetition, and gap injection rates."""
        conn = self._connect()
        c = conn.cursor()
        if session_id:
            c.execute(
                "SELECT id, prompt_text, intent_category, reasoning_type, failure_detected, created_at "
                "FROM prompt_sessions WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit)
            )
        else:
            c.execute(
                "SELECT id, prompt_text, intent_category, reasoning_type, failure_detected, created_at "
                "FROM prompt_sessions ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
        rows = c.fetchall()
        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)

        if not rows:
            return {"total_prompts": 0, "patterns": [], "health": "no_data"}

        # Analyze patterns
        total = len(rows)
        loop_kicks = sum(1 for r in rows if r[3] in ('loop_continuation', 'loop_kick'))
        gap_injections = sum(1 for r in rows if r[3] in ('gap_injection', 'anticipation_failure'))
        depth_rejections = sum(1 for r in rows if r[3] in ('depth_rejection', 'depth_escalation'))
        detection_failures = sum(1 for r in rows if r[4])  # failure_detected is non-empty

        # Calculate health score (0-100, lower = worse)
        # Perfect system: 0 loop kicks, 0 gap injections, 0 depth rejections
        waste_ratio = (loop_kicks + gap_injections + depth_rejections) / max(total, 1)
        health_score = max(0, int(100 * (1 - waste_ratio)))

        patterns = []
        if loop_kicks > 0:
            patterns.append({"type": "LOOP_FAILURE", "count": loop_kicks,
                           "pct": round(100 * loop_kicks / total, 1),
                           "fix": "System stops when it should continue. Set auto_continue=True after 2+ go prompts."})
        if gap_injections > 0:
            patterns.append({"type": "ANTICIPATION_FAILURE", "count": gap_injections,
                           "pct": round(100 * gap_injections / total, 1),
                           "fix": "Run architecture checklist internally before presenting designs."})
        if depth_rejections > 0:
            patterns.append({"type": "DEPTH_FAILURE", "count": depth_rejections,
                           "pct": round(100 * depth_rejections / total, 1),
                           "fix": "Gap-analyze instead of pattern-matching. Check what was NOT mentioned."})

        return {
            "total_prompts": total,
            "substantive_prompts": total - loop_kicks - gap_injections - depth_rejections,
            "waste_prompts": loop_kicks + gap_injections + depth_rejections,
            "health_score": health_score,
            "health": "healthy" if health_score >= 80 else "degraded" if health_score >= 50 else "critical",
            "patterns": patterns,
            "detection_failures": detection_failures
        }

    def get_user_thinking_model(self) -> list[dict]:
        """Return the current model of how the user thinks."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "SELECT pattern_name, evidence_count, example_prompts, system_adaptation, confidence, last_seen "
            "FROM user_thinking_patterns ORDER BY confidence DESC"
        )
        results = [{"pattern": r[0], "evidence": r[1], "examples": r[2],
                     "adaptation": r[3], "confidence": r[4], "last_seen": r[5]}
                    for r in c.fetchall()]
        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)
        return results

    def update_thinking_pattern(self, pattern_name: str, system_adaptation: str,
                                 example_prompt: str = '') -> str:
        """Update or create a user thinking pattern."""
        import json
        conn = self._connect()
        c = conn.cursor()
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        c.execute("SELECT id, evidence_count, example_prompts, confidence FROM user_thinking_patterns WHERE pattern_name = ?",
                  (pattern_name,))
        existing = c.fetchone()
        if existing:
            new_count = existing[1] + 1
            try:
                examples = json.loads(existing[2])
            except (json.JSONDecodeError, TypeError):
                examples = []
            if example_prompt:
                examples.append(example_prompt)
                examples = examples[-10:]  # Keep last 10
            new_confidence = min(1.0, existing[3] + 0.05)  # Increase confidence with each observation
            c.execute(
                "UPDATE user_thinking_patterns SET evidence_count = ?, example_prompts = ?, "
                "confidence = ?, system_adaptation = ?, last_seen = ? WHERE id = ?",
                (new_count, json.dumps(examples), new_confidence, system_adaptation, now, existing[0])
            )
            action = f"Updated pattern '{pattern_name}' (evidence: {new_count}, confidence: {new_confidence:.2f})"
        else:
            examples = [example_prompt] if example_prompt else []
            c.execute(
                "INSERT INTO user_thinking_patterns (pattern_name, evidence_count, example_prompts, "
                "system_adaptation, confidence, last_seen) VALUES (?, 1, ?, ?, 0.5, ?)",
                (pattern_name, json.dumps(examples), system_adaptation, now)
            )
            action = f"Created new pattern '{pattern_name}' (confidence: 0.50)"
        self._close(conn)
        return action

    # ==================== TOOL USAGE TRACKING ====================

    def log_tool_usage(self, tool_name: str, args_summary: str = '',
                       result_summary: str = '', session_id: str = '',
                       duration_ms: int = 0) -> int:
        """Log a tool invocation for usage analytics."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            """INSERT INTO tool_usage_log 
               (tool_name, args_summary, result_summary, session_id, duration_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (tool_name, (args_summary or '')[:500], (result_summary or '')[:500], session_id,
             duration_ms, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
        )
        row_id = c.lastrowid
        self._close(conn)
        return row_id

    def get_tool_usage_stats(self, days: int = 7) -> dict:
        """Get tool usage statistics for the last N days."""
        conn = self._connect()
        c = conn.cursor()
        cutoff = time.strftime("%Y-%m-%d %H:%M:%S",
                               time.gmtime(time.time() - max(1, days) * 86400))
        c.execute(
            "SELECT tool_name, COUNT(*) as cnt FROM tool_usage_log "
            "WHERE created_at >= ? GROUP BY tool_name ORDER BY cnt DESC",
            (cutoff,)
        )
        usage = {r[0]: r[1] for r in c.fetchall()}
        c.execute("SELECT COUNT(*) FROM tool_usage_log WHERE created_at >= ?", (cutoff,))
        total = c.fetchone()[0]
        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)
        # Find never-used tools (would need tool registry — return what we have)
        return {
            "total_invocations": total,
            "by_tool": usage,
            "most_used": list(usage.keys())[:5] if usage else [],
            "period_days": days
        }

    # ==================== MISSED DETECTIONS ====================

    def record_missed_detection(self, detection_type: str, what_was_missed: str,
                                 root_cause: str, prevention_rule: str,
                                 trigger_prompt_id: int = None) -> int:
        """Record something the system should have caught but didn't.
        ChatGPT §4 fix: Auto-generates a prevention rule to close the learn→prevent loop."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            """INSERT INTO missed_detections 
               (trigger_prompt_id, detection_type, what_was_missed, root_cause,
                prevention_rule, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (trigger_prompt_id, detection_type, what_was_missed, root_cause,
             prevention_rule, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
        )
        row_id = c.lastrowid
        self._close(conn)

        # ── AUTO-RULE GENERATION (ChatGPT §4/§8: close feedback loop) ──
        # If the missed detection suggests a prevention rule, auto-create it
        if prevention_rule and prevention_rule.strip():
            # Determine trigger event from detection type
            trigger_map = {
                'anti_pattern': 'prompt.received',
                'security': 'phase.before:code_change',
                'quality': 'phase.after:code_change',
                'design': 'phase.before:design',
                'test': 'phase.after:code_change',
            }
            trigger = trigger_map.get(detection_type, 'tool.after:*')
            rule_name = f"auto_{detection_type}_{row_id}"
            try:
                self.register_prevention_rule(
                    rule_name=rule_name,
                    trigger_event=trigger,
                    check_query=what_was_missed[:500],
                    action_on_match=prevention_rule[:500],
                    severity='P1',
                    source_detection_id=row_id,
                )
            except Exception:
                pass  # Rule may already exist — idempotent

        return row_id

    def get_unautomated_detections(self) -> list[dict]:
        """Get missed detections that haven't been converted to prevention rules yet."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "SELECT id, detection_type, what_was_missed, root_cause, prevention_rule, created_at "
            "FROM missed_detections WHERE automated = 0 ORDER BY created_at DESC"
        )
        results = [{"id": r[0], "type": r[1], "missed": r[2], "root_cause": r[3],
                     "prevention_rule": r[4], "created_at": r[5]} for r in c.fetchall()]
        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)
        return results

    # ==================== PREVENTION RULES ====================

    def register_prevention_rule(self, rule_name: str, trigger_event: str,
                                  check_query: str, action_on_match: str,
                                  severity: str = 'P1',
                                  source_detection_id: int = None) -> str:
        """Register an automated prevention rule derived from a missed detection."""
        conn = self._connect()
        c = conn.cursor()
        try:
            c.execute(
                """INSERT INTO prevention_rules 
                   (rule_name, trigger_event, check_query, action_on_match,
                    severity, source_detection_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (rule_name, trigger_event, check_query, action_on_match,
                 severity, source_detection_id, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
            )
            # Mark the source detection as automated
            if source_detection_id:
                c.execute("UPDATE missed_detections SET automated = 1 WHERE id = ?",
                          (source_detection_id,))
            self._close(conn)
            return f"Prevention rule '{rule_name}' registered (severity: {severity})"
        except Exception as e:
            if 'UNIQUE' in str(e):
                # Update existing rule
                c.execute(
                    "UPDATE prevention_rules SET check_query = ?, action_on_match = ?, "
                    "severity = ? WHERE rule_name = ?",
                    (check_query, action_on_match, severity, rule_name)
                )
                self._close(conn)
                return f"Prevention rule '{rule_name}' updated"
            self._close(conn)
            raise

    def get_active_prevention_rules(self, trigger_event: str = '') -> list[dict]:
        """Get all active prevention rules, optionally filtered by trigger event."""
        conn = self._connect()
        c = conn.cursor()
        if trigger_event:
            c.execute(
                "SELECT id, rule_name, trigger_event, check_query, action_on_match, "
                "severity, times_triggered FROM prevention_rules WHERE enabled = 1 AND trigger_event = ?",
                (trigger_event,)
            )
        else:
            c.execute(
                "SELECT id, rule_name, trigger_event, check_query, action_on_match, "
                "severity, times_triggered FROM prevention_rules WHERE enabled = 1"
            )
        results = [{"id": r[0], "rule_name": r[1], "trigger_event": r[2], "check_query": r[3],
                     "action": r[4], "severity": r[5], "times_triggered": r[6]}
                    for r in c.fetchall()]
        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)
        return results

    def increment_rule_trigger(self, rule_id: int) -> None:
        """Increment the trigger count for a prevention rule."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("UPDATE prevention_rules SET times_triggered = times_triggered + 1 WHERE id = ?",
                  (rule_id,))
        self._close(conn)

    def log_injection(self, session_id: str, anti_pattern_ids: list[int], prompt_hash: str, prompt_embedding=None):
        """Record an anti-pattern injection event for feedback loop measurement."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO injection_events (session_id, prompt_hash, prompt_embedding, anti_pattern_ids, injected_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, prompt_hash, prompt_embedding, json.dumps(anti_pattern_ids), time.time())
        )
        conn.commit()
        return c.lastrowid

    def resolve_injection(self, injection_id: int, outcome: str, recurrence_id: int = None):
        """Resolve an injection event outcome: 'prevented' or 'recurred'."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "UPDATE injection_events SET outcome = ?, resolved_at = ?, recurrence_anti_pattern_id = ? WHERE id = ?",
            (outcome, time.time(), recurrence_id, injection_id)
        )
        conn.commit()

    def get_recent_injections(self, session_id: str, since: float = None) -> list[dict]:
        """Get recent injection events for a session."""
        conn = self._connect()
        c = conn.cursor()
        if since is None:
            since = time.time() - 1800  # last 30 minutes
        c.execute(
            "SELECT id, session_id, prompt_hash, anti_pattern_ids, injected_at, outcome "
            "FROM injection_events WHERE session_id = ? AND injected_at > ? ORDER BY injected_at DESC",
            (session_id, since)
        )
        return [{'id': r[0], 'session_id': r[1], 'prompt_hash': r[2], 'anti_pattern_ids': json.loads(r[3]),
                 'injected_at': r[4], 'outcome': r[5]} for r in c.fetchall()]

    def get_injection_prevention_rate(self) -> dict:
        """Calculate the prevention rate from injection events."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT outcome, COUNT(*) FROM injection_events WHERE outcome != 'unknown' GROUP BY outcome")
        counts = dict(c.fetchall())
        prevented = counts.get('prevented', 0)
        recurred = counts.get('recurred', 0)
        total = prevented + recurred
        return {
            'prevented': prevented,
            'recurred': recurred,
            'total': total,
            'prevention_rate': round(prevented / total, 3) if total > 0 else None
        }

    def record_thought(self, session_id: str, thought_id: str, branch_id: str, content: str,
                       thought_type: str = 'hypothesis', parent_thought_id: str = None,
                       confidence: float = None, related_decision_id: int = None) -> dict:
        """Record a thought in the reasoning trace."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO reasoning_traces (session_id, thought_id, branch_id, parent_thought_id, "
            "thought_type, content, confidence, created_at, related_decision_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, thought_id, branch_id, parent_thought_id, thought_type,
             content, confidence, time.time(), related_decision_id)
        )
        conn.commit()
        return {'thought_id': thought_id, 'branch_id': branch_id, 'id': c.lastrowid}

    def revise_thought(self, session_id: str, old_thought_id: str, new_thought_id: str,
                       new_content: str, reason: str) -> dict:
        """Create a revision that supersedes an existing thought."""
        conn = self._connect()
        c = conn.cursor()
        # Get the original thought
        c.execute("SELECT branch_id, thought_type FROM reasoning_traces WHERE session_id = ? AND thought_id = ?",
                  (session_id, old_thought_id))
        row = c.fetchone()
        if not row:
            return {'error': f'Thought {old_thought_id} not found'}
        branch_id, thought_type = row
        # Mark old as superseded
        c.execute("UPDATE reasoning_traces SET status = 'superseded', superseded_by = ? "
                  "WHERE session_id = ? AND thought_id = ?",
                  (new_thought_id, session_id, old_thought_id))
        # Create new thought
        c.execute(
            "INSERT INTO reasoning_traces (session_id, thought_id, branch_id, parent_thought_id, "
            "thought_type, content, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'open', ?)",
            (session_id, new_thought_id, branch_id, old_thought_id, 'revision',
             f"{new_content}\n\n[Revision reason: {reason}]", time.time())
        )
        conn.commit()
        return {'thought_id': new_thought_id, 'supersedes': old_thought_id}

    def create_branch(self, session_id: str, branch_id: str, from_thought_id: str, reason: str) -> dict:
        """Fork a new reasoning branch from a thought."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO reasoning_branches (branch_id, session_id, forked_from_thought_id, "
            "fork_reason, created_at) VALUES (?, ?, ?, ?, ?)",
            (branch_id, session_id, from_thought_id, reason, time.time())
        )
        conn.commit()
        return {'branch_id': branch_id, 'forked_from': from_thought_id}

    def get_branch_trace(self, session_id: str, branch_id: str = 'main') -> list[dict]:
        """Get ordered thought chain for a branch."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "SELECT thought_id, parent_thought_id, thought_type, content, confidence, status, created_at "
            "FROM reasoning_traces WHERE session_id = ? AND branch_id = ? ORDER BY created_at ASC",
            (session_id, branch_id)
        )
        traces = [{'thought_id': r[0], 'parent': r[1], 'type': r[2], 'content': r[3],
                 'confidence': r[4], 'status': r[5], 'created_at': r[6]} for r in c.fetchall()]
        # Wire temporal_confidence: compute live confidence for each trace
        try:
            from core.memory.temporal_confidence import current_confidence
            for trace in traces:
                trace['live_confidence'] = current_confidence(trace)
        except Exception:
            pass  # Never break trace retrieval if temporal_confidence unavailable
        return traces

    def conclude_branch(self, session_id: str, branch_id: str, winning_thought_id: str) -> dict:
        """Mark a branch as winning and others as abandoned."""
        conn = self._connect()
        c = conn.cursor()
        # Mark winning branch
        c.execute(
            "UPDATE reasoning_branches SET status = 'winning', winning_thought_id = ?, closed_at = ? "
            "WHERE session_id = ? AND branch_id = ?",
            (winning_thought_id, time.time(), session_id, branch_id)
        )
        # Mark other branches abandoned
        c.execute(
            "UPDATE reasoning_branches SET status = 'abandoned', closed_at = ? "
            "WHERE session_id = ? AND branch_id != ? AND status = 'active'",
            (time.time(), session_id, branch_id)
        )
        conn.commit()
        return {'winning_branch': branch_id, 'winning_thought': winning_thought_id}

    def update_rule_evaluation(self, rule_id: int, error: str = None, check_ms: float = None):
        """Update prevention rule observability metrics."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "UPDATE prevention_rules SET last_evaluated_at = ?, evaluation_count = evaluation_count + 1, "
            "last_error = ?, last_check_query_ms = ? WHERE id = ?",
            (time.time(), error, check_ms, rule_id)
        )
        conn.commit()

    # ==================== AUTONOMOUS GAP DETECTION ====================

    def autonomous_scan(self) -> dict:
        """Run the autonomous gap detector. Checks for unresolved issues across all subsystems."""
        gaps = []

        # 1. Check unresolved missed detections
        unresolved = self.get_unautomated_detections()
        if unresolved:
            gaps.append({
                "source": "missed_detections",
                "severity": "P0",
                "count": len(unresolved),
                "detail": f"{len(unresolved)} missed detections not yet converted to prevention rules",
                "action": "Call register_prevention_rule for each",
                "auto_executable": False
            })

        # 2. Check stale goals (active goals with no progress update in 7 days)
        conn = self._connect()
        c = conn.cursor()
        cutoff = time.strftime("%Y-%m-%d %H:%M:%S",
                               time.gmtime(time.time() - 7 * 86400))
        c.execute(
            "SELECT COUNT(*) FROM goals WHERE status = 'active' AND updated_at < ?",
            (cutoff,)
        )
        stale_goals = c.fetchone()[0]
        if stale_goals > 0:
            gaps.append({
                "source": "goals",
                "severity": "P1",
                "count": stale_goals,
                "detail": f"{stale_goals} active goals with no update in 7+ days",
                "action": "Review and update or archive stale goals",
                "auto_executable": False
            })

        # 3. Check quality regression
        trend = self.get_quality_trend()
        if trend.get("trend") == "declining":
            gaps.append({
                "source": "quality_scores",
                "severity": "P0",
                "count": 1,
                "detail": f"Quality trend is DECLINING (avg: {trend.get('recent_avg', 0):.1f} → {trend.get('older_avg', 0):.1f})",
                "action": "Investigate root cause of quality regression",
                "auto_executable": False
            })

        # 4. Check unresolved predictions
        try:
            unresolved_preds = self.graph.get_unresolved_predictions()
            expired = [p for p in unresolved_preds
                       if p.get('created_at', '') < cutoff]
            if expired:
                gaps.append({
                    "source": "predictions",
                    "severity": "P2",
                    "count": len(expired),
                    "detail": f"{len(expired)} predictions pending for 7+ days",
                    "action": "Resolve or update expired predictions",
                    "auto_executable": False
                })
        except Exception:
            pass

        # 5. Check prompt health
        prompt_analysis = self.analyze_prompt_sequence(limit=50)
        if prompt_analysis.get("health") == "critical":
            gaps.append({
                "source": "prompt_intelligence",
                "severity": "P0",
                "count": prompt_analysis.get("waste_prompts", 0),
                "detail": f"User satisfaction critically low — {prompt_analysis.get('waste_prompts', 0)} wasted prompts out of {prompt_analysis.get('total_prompts', 0)}",
                "action": "Review and address the dominant failure patterns",
                "auto_executable": False
            })

        # 6. Check prevention rule effectiveness
        rules = self.get_active_prevention_rules()
        never_triggered = [r for r in rules if r.get('times_triggered', 0) == 0]
        if len(never_triggered) > len(rules) * 0.5 and len(rules) > 5:
            gaps.append({
                "source": "prevention_rules",
                "severity": "P2",
                "count": len(never_triggered),
                "detail": f"{len(never_triggered)} of {len(rules)} prevention rules never triggered — may be misconfigured",
                "action": "Review and update or disable ineffective rules",
                "auto_executable": True
            })

        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)

        return {
            "total_gaps": len(gaps),
            "p0_count": sum(1 for g in gaps if g['severity'] == 'P0'),
            "p1_count": sum(1 for g in gaps if g['severity'] == 'P1'),
            "p2_count": sum(1 for g in gaps if g['severity'] == 'P2'),
            "gaps": sorted(gaps, key=lambda g: {'P0': 0, 'P1': 1, 'P2': 2}.get(g['severity'], 3)),
            "scan_time": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        }

    def self_diagnose(self) -> dict:
        """Run a full diagnostic of the adaptive learning system's health."""
        conn = self._connect()
        c = conn.cursor()

        # Prevention rules stats
        c.execute("SELECT COUNT(*) FROM prevention_rules WHERE enabled = 1")
        active_rules = c.fetchone()[0]
        c.execute("SELECT SUM(times_triggered) FROM prevention_rules")
        total_triggers = c.fetchone()[0] or 0

        # Prompt stats
        c.execute("SELECT COUNT(*) FROM prompt_sessions")
        total_prompts = c.fetchone()[0]

        # Missed detection stats
        c.execute("SELECT COUNT(*) FROM missed_detections")
        total_missed = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM missed_detections WHERE automated = 1")
        automated_missed = c.fetchone()[0]

        # Tool usage stats
        c.execute("SELECT COUNT(DISTINCT tool_name) FROM tool_usage_log")
        unique_tools = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM tool_usage_log")
        total_tool_calls = c.fetchone()[0]

        # User thinking patterns
        c.execute("SELECT COUNT(*) FROM user_thinking_patterns")
        pattern_count = c.fetchone()[0]

        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)

        # Calculate autonomy rate
        autonomy_rate = (automated_missed / max(total_missed, 1)) * 100

        return {
            "prevention_rules": {"active": active_rules, "total_triggers": total_triggers},
            "prompt_intelligence": {"total_prompts": total_prompts, "patterns_learned": pattern_count},
            "missed_detections": {"total": total_missed, "automated": automated_missed,
                                   "pending": total_missed - automated_missed},
            "tool_usage": {"unique_tools": unique_tools, "total_calls": total_tool_calls},
            "autonomy_rate": round(autonomy_rate, 1),
            "health": "elite" if autonomy_rate >= 80 else "growing" if autonomy_rate >= 40 else "nascent",
            "diagnosed_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        }

    # ==================== AUTONOMOUS GOAL ENGINE ====================

    def generate_autonomous_goals(self) -> list[dict]:
        """Analyze all data sources and generate prioritized autonomous goals."""
        goals = []

        # 1. From missed detections: reduce recurring failure types
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "SELECT detection_type, COUNT(*) as cnt FROM missed_detections "
            "GROUP BY detection_type ORDER BY cnt DESC"
        )
        for row in c.fetchall():
            if row[1] >= 2:  # Pattern seen 2+ times
                goals.append({
                    "source": "missed_detections",
                    "objective": f"Eliminate {row[0]} failures (seen {row[1]} times)",
                    "priority": "P0" if row[1] >= 5 else "P1",
                    "auto_executable": False,
                    "confidence": min(0.9, 0.5 + row[1] * 0.1)
                })

        # 2. From quality trend: if declining, create improvement goal
        trend = self.get_quality_trend()
        if trend.get("trend") == "declining":
            goals.append({
                "source": "quality_scores",
                "objective": "Reverse quality decline — investigate and fix root causes",
                "priority": "P0",
                "auto_executable": False,
                "confidence": 0.8
            })

        # 3. From unautomated detections: convert to prevention rules
        pending = self.get_unautomated_detections()
        if pending:
            goals.append({
                "source": "prevention_rules",
                "objective": f"Convert {len(pending)} missed detections into prevention rules",
                "priority": "P1",
                "auto_executable": True,
                "confidence": 0.9
            })

        # 4. From prompt analysis: address dominant failure type
        analysis = self.analyze_prompt_sequence(limit=50)
        for pattern in analysis.get("patterns", []):
            if pattern.get("pct", 0) > 20:  # Over 20% of prompts
                goals.append({
                    "source": "prompt_intelligence",
                    "objective": f"Fix {pattern['type']}: {pattern.get('fix', 'unknown')}",
                    "priority": "P0" if pattern['pct'] > 30 else "P1",
                    "auto_executable": False,
                    "confidence": 0.7
                })

        if not getattr(self._local, 'in_transaction', False):
            self._close(conn)

        return sorted(goals, key=lambda g: {'P0': 0, 'P1': 1, 'P2': 2}.get(g['priority'], 3))

    def get_autonomous_status(self) -> dict:
        """Return what the system has been doing autonomously."""
        diagnosis = self.self_diagnose()
        goals = self.generate_autonomous_goals()
        scan = self.autonomous_scan()

        return {
            "diagnosis": diagnosis,
            "autonomous_goals": goals,
            "gap_scan": scan,
            "summary": (
                f"System health: {diagnosis['health']}. "
                f"Autonomy rate: {diagnosis['autonomy_rate']}%. "
                f"{scan['total_gaps']} gaps found ({scan['p0_count']} P0). "
                f"{len(goals)} autonomous goals generated."
            )
        }

    # ==================== CALIBRATION LOG (P3) ====================

    def log_calibration(self, prediction_id: str, claim: str, confidence: float,
                        domain: str = "general") -> int:
        """Log a confidence prediction for later calibration."""
        conn = self._connect()
        c = conn.cursor()
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        c.execute("""INSERT INTO calibration_log
                     (prediction_id, claim, confidence, domain, created_at)
                     VALUES (?, ?, ?, ?, ?)""",
                  (prediction_id, claim[:1000], max(0.0, min(1.0, confidence)),
                   domain, now))
        conn.commit()
        row_id = c.lastrowid
        self._close(conn)
        return row_id

    def resolve_calibration(self, prediction_id: str, outcome: str,
                            correct: bool) -> bool:
        """Resolve a calibration prediction with actual outcome."""
        conn = self._connect()
        c = conn.cursor()
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        c.execute("""UPDATE calibration_log SET outcome = ?, outcome_correct = ?,
                     resolved_at = ? WHERE prediction_id = ? AND outcome_correct IS NULL""",
                  (outcome[:500], 1 if correct else 0, now, prediction_id))
        conn.commit()
        updated = c.rowcount > 0
        self._close(conn)
        return updated

    def get_calibration_score(self, domain: str = None, days: int = 30) -> dict:
        """Compute Brier score and calibration metrics."""
        conn = self._connect()
        c = conn.cursor()
        cutoff = time.strftime("%Y-%m-%d %H:%M:%S",
                               time.gmtime(time.time() - max(1, days) * 86400))
        if domain:
            c.execute("""SELECT confidence, outcome_correct FROM calibration_log
                        WHERE outcome_correct IS NOT NULL AND domain = ?
                        AND created_at > ? ORDER BY created_at DESC LIMIT 500""",
                      (domain, cutoff))
        else:
            c.execute("""SELECT confidence, outcome_correct FROM calibration_log
                        WHERE outcome_correct IS NOT NULL AND created_at > ?
                        ORDER BY created_at DESC LIMIT 500""", (cutoff,))
        rows = c.fetchall()
        self._close(conn)

        if not rows:
            return {"brier_score": None, "total_predictions": 0,
                    "calibration": "no data"}

        # Brier score: mean squared error of confidence vs binary outcome
        brier = sum((conf - actual) ** 2 for conf, actual in rows) / len(rows)
        accuracy = sum(1 for _, actual in rows if actual == 1) / len(rows)
        avg_confidence = sum(conf for conf, _ in rows) / len(rows)
        overconfident = avg_confidence > accuracy + 0.1
        underconfident = avg_confidence < accuracy - 0.1

        # Bucket calibration (10 buckets)
        buckets = {}
        for conf, actual in rows:
            bucket = min(9, int(conf * 10))
            if bucket not in buckets:
                buckets[bucket] = {"total": 0, "correct": 0, "sum_conf": 0.0}
            buckets[bucket]["total"] += 1
            buckets[bucket]["correct"] += actual
            buckets[bucket]["sum_conf"] += conf

        calibration_table = []
        for b in sorted(buckets.keys()):
            d = buckets[b]
            actual_rate = d["correct"] / d["total"] if d["total"] > 0 else 0
            expected_rate = d["sum_conf"] / d["total"] if d["total"] > 0 else 0
            calibration_table.append({
                "bucket": f"{b*10}-{(b+1)*10}%",
                "count": d["total"],
                "expected": round(expected_rate, 3),
                "actual": round(actual_rate, 3),
                "gap": round(abs(expected_rate - actual_rate), 3)
            })

        return {
            "brier_score": round(brier, 4),
            "total_predictions": len(rows),
            "accuracy": round(accuracy, 3),
            "avg_confidence": round(avg_confidence, 3),
            "calibration_status": "overconfident" if overconfident else
                                  "underconfident" if underconfident else "calibrated",
            "calibration_table": calibration_table
        }

    # ==================== DECISION COUNCIL (P3) ====================

    def add_council_review(self, decision_id: int, decision_text: str,
                           perspective: str, critique: str,
                           risk_flags: list, recommendation: str,
                           confidence: float = 0.5) -> int:
        """Store a decision council perspective review."""
        conn = self._connect()
        c = conn.cursor()
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        c.execute("""INSERT INTO decision_council
                     (decision_id, decision_text, perspective, critique,
                      risk_flags, recommendation, confidence, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                  (decision_id, decision_text[:500], perspective,
                   critique[:1000], json.dumps(risk_flags[:10]),
                   recommendation, max(0.0, min(1.0, confidence)), now))
        conn.commit()
        row_id = c.lastrowid
        self._close(conn)
        return row_id

    def get_council_reviews(self, decision_id: int) -> list:
        """Get all council reviews for a decision."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("""SELECT perspective, critique, risk_flags, recommendation,
                     confidence, created_at FROM decision_council
                     WHERE decision_id = ? ORDER BY created_at""",
                  (decision_id,))
        rows = c.fetchall()
        self._close(conn)
        return [{"perspective": r[0], "critique": r[1],
                 "risk_flags": json.loads(r[2] or "[]"),
                 "recommendation": r[3], "confidence": r[4],
                 "created_at": r[5]} for r in rows]

    # ==================== COST TRACKING (Opus R2 Q13b) ====================

    def log_cost(self, cost_type: str, units: float = 0, estimated_usd: float = 0,
                 provider: str = 'local', tool_name: str = None,
                 session_id: str = 'default') -> int:
        """Log an API/embedding/compute cost event."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("""INSERT INTO cost_log
                     (session_id, tool_name, cost_type, provider, units, estimated_usd, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (session_id, tool_name, cost_type, provider, units, estimated_usd, time.time()))
        row_id = c.lastrowid
        self._close(conn)
        return row_id

    def get_cost_summary(self, days: int = 7) -> dict:
        """Cost summary by type over N days."""
        conn = self._connect()
        c = conn.cursor()
        cutoff = time.time() - (days * 86400)
        c.execute("""SELECT cost_type, provider, COUNT(*) as count,
                     SUM(units) as total_units, SUM(estimated_usd) as total_usd
                     FROM cost_log WHERE created_at > ?
                     GROUP BY cost_type, provider ORDER BY total_usd DESC""",
                  (cutoff,))
        rows = c.fetchall()
        self._close(conn)
        return {
            "period_days": days,
            "breakdown": [{"cost_type": r[0], "provider": r[1], "count": r[2],
                           "total_units": r[3], "total_usd": round(r[4], 6)}
                          for r in rows],
            "total_usd": round(sum(r[4] for r in rows), 6),
        }

    # ==================== ADVERSARIAL INPUT HANDLING (Opus R2 Q13c) ====================

    def quarantine_anti_pattern(self, pattern_id: int, reason: str = 'adversarial') -> bool:
        """Quarantine an anti-pattern: mark untrusted, exclude from injection."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("""UPDATE anti_patterns SET quarantined = 1,
                     injection_eligible = 0, injection_disabled_reason = ?,
                     trust_score = 0.0 WHERE id = ?""",
                  (reason, pattern_id))
        affected = c.rowcount
        self._close(conn)
        return affected > 0

    def release_quarantine(self, pattern_id: int) -> bool:
        """Release an anti-pattern from quarantine after human review."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("""UPDATE anti_patterns SET quarantined = 0,
                     injection_eligible = 1, injection_disabled_reason = NULL,
                     trust_score = 0.3, source = 'human_verified'
                     WHERE id = ? AND quarantined = 1""",
                  (pattern_id,))
        affected = c.rowcount
        self._close(conn)
        return affected > 0

    # ==================== RULE LIFECYCLE (Opus R2 Q6) ====================

    def update_rule_lifecycle(self, rule_id: int, new_state: str,
                              true_positives: int = None,
                              false_positives: int = None) -> bool:
        """Update a prevention rule's lifecycle state.
        States: probation → active → trusted → retired
        Rules must earn their way to 'trusted' via demonstrated value."""
        valid_states = ('probation', 'active', 'trusted', 'retired')
        if new_state not in valid_states:
            return False
        conn = self._connect()
        c = conn.cursor()
        now = time.time()
        # Use explicit branches instead of dynamic SQL construction
        if new_state == 'active':
            c.execute(
                "UPDATE prevention_rules SET lifecycle_state = ?, promoted_at = ? WHERE id = ?",
                (new_state, now, rule_id)
            )
        elif new_state == 'retired':
            c.execute(
                "UPDATE prevention_rules SET lifecycle_state = ?, retired_at = ?, enabled = 0 WHERE id = ?",
                (new_state, now, rule_id)
            )
        else:
            c.execute(
                "UPDATE prevention_rules SET lifecycle_state = ? WHERE id = ?",
                (new_state, rule_id)
            )
        # Update optional counters separately (safe parameterized queries)
        if true_positives is not None:
            c.execute(
                "UPDATE prevention_rules SET true_positive_count = ? WHERE id = ?",
                (true_positives, rule_id)
            )
        if false_positives is not None:
            c.execute(
                "UPDATE prevention_rules SET false_positive_count = ? WHERE id = ?",
                (false_positives, rule_id)
            )
        affected = c.rowcount
        self._close(conn)
        return affected > 0

    def get_rule_lifecycle_summary(self) -> dict:
        """Summary of prevention rules by lifecycle state."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("""SELECT lifecycle_state, COUNT(*), SUM(times_triggered),
                     SUM(true_positive_count), SUM(false_positive_count)
                     FROM prevention_rules GROUP BY lifecycle_state""")
        rows = c.fetchall()
        self._close(conn)
        return {
            "by_state": {r[0] or 'unknown': {
                "count": r[1], "total_fires": r[2] or 0,
                "true_positives": r[3] or 0, "false_positives": r[4] or 0}
                for r in rows},
            "total_rules": sum(r[1] for r in rows),
        }

    # ==================== TRIGGER EFFECTIVENESS (Opus R2 Q4) ====================

    def record_trigger_effectiveness(self, detection_type: str,
                                      trigger_event: str,
                                      quality_improved: bool = False,
                                      quality_degraded: bool = False,
                                      mistake_prevented: bool = False):
        """Record whether a trigger firing improved quality."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("""INSERT INTO trigger_effectiveness
                     (detection_type, trigger_event, fired_count,
                      quality_improved_count, quality_degraded_count,
                      mistake_prevented_count, last_updated)
                     VALUES (?, ?, 1, ?, ?, ?, ?)
                     ON CONFLICT(detection_type, trigger_event) DO UPDATE SET
                     fired_count = fired_count + 1,
                     quality_improved_count = quality_improved_count + ?,
                     quality_degraded_count = quality_degraded_count + ?,
                     mistake_prevented_count = mistake_prevented_count + ?,
                     last_updated = ?""",
                  (detection_type, trigger_event,
                   int(quality_improved), int(quality_degraded), int(mistake_prevented),
                   time.time(),
                   int(quality_improved), int(quality_degraded), int(mistake_prevented),
                   time.time()))
        self._close(conn)

    def get_trigger_report(self) -> dict:
        """Which triggers are effective vs noisy?"""
        conn = self._connect()
        c = conn.cursor()
        c.execute("""SELECT detection_type, trigger_event, fired_count,
                     quality_improved_count, quality_degraded_count,
                     mistake_prevented_count FROM trigger_effectiveness
                     ORDER BY fired_count DESC LIMIT 50""")
        rows = c.fetchall()
        self._close(conn)
        return {
            "triggers": [{
                "detection_type": r[0], "trigger_event": r[1],
                "fired": r[2], "quality_improved": r[3],
                "quality_degraded": r[4], "mistakes_prevented": r[5],
                "effectiveness_ratio": round(
                    (r[3] + r[5]) / max(r[2], 1), 3)
            } for r in rows]
        }

