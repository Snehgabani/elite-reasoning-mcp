"""
Persistent local storage for the Elite MCP Server.
Handles ONLY our unique moat: anti-patterns, decisions, quality scores,
benchmarks, goals, smoke tests, and after-action reviews.
Memory/context is delegated to AgentMemory or Mem0.
"""
import os
import sqlite3
import time
import json
import threading
import contextlib

try:
    import sqlite_vec
    import struct
except ImportError:
    sqlite_vec = None

from core.memory.graph_store import TemporalGraphStore


class EliteStore:
    """Local SQLite store for anti-patterns, decisions, quality, benchmarks, goals, and reviews."""

    def __init__(self, brain_dir: str):
        self.brain_dir = brain_dir
        self.db_path = os.path.join(brain_dir, "elite.db")
        self._local = threading.local()
        os.makedirs(brain_dir, exist_ok=True)
        self._init_db()
        self.graph = TemporalGraphStore(self.db_path)  # Same DB — single transaction boundary

    def _connect(self) -> sqlite3.Connection:
        cached = getattr(self._local, 'conn', None)
        if cached is not None:
            # Verify the cached connection is still usable
            try:
                cached.execute("SELECT 1")
                return cached
            except Exception:
                # Stale/closed connection — clear cache and create new
                self._local.conn = None
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=120000;")
        if sqlite_vec is not None:
            conn.enable_load_extension(True)
            try:
                sqlite_vec.load(conn)
            except Exception:
                pass
        # Cache on _local so subsequent calls reuse this connection
        self._local.conn = conn
        return conn

    def _close(self, conn):
        if getattr(self._local, 'in_transaction', False):
            return
        conn.commit()
        conn.close()
        # Clear cache so next _connect opens a fresh connection
        self._local.conn = None

    @contextlib.contextmanager
    def transaction(self):
        if getattr(self._local, 'in_transaction', False):
            yield
            return

        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=120000;")
        if sqlite_vec is not None:
            conn.enable_load_extension(True)
            try:
                sqlite_vec.load(conn)
            except Exception:
                pass
        
        conn.isolation_level = None
        self._local.in_transaction = True
        self._local.conn = conn
        
        graph_conn = sqlite3.connect(self.graph.db_path, check_same_thread=False, timeout=30.0)
        graph_conn.row_factory = sqlite3.Row
        graph_conn.isolation_level = None
        self.graph._local.in_transaction = True
        self.graph._local.conn = graph_conn

        try:
            conn.execute("BEGIN IMMEDIATE")
            graph_conn.execute("BEGIN IMMEDIATE")
            yield
            conn.execute("COMMIT")
            graph_conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            graph_conn.execute("ROLLBACK")
            raise
        finally:
            self._local.in_transaction = False
            self._local.conn = None
            self.graph._local.in_transaction = False
            self.graph._local.conn = None
            conn.close()
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
                created_at TEXT NOT NULL
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
        ]
        for stmt in index_stmts:
            c.execute(stmt)

        self._close(conn)

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
            from core.memory.embedding import get_embedding
            import os
            os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
            return get_embedding(text)
        except Exception:
            return None

    def record_mistake(self, mistake: str, root_cause: str, fix: str, severity: str = "medium", tags: str = "") -> int:
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
                    # Duplicate detected — skip insertion
                    if not getattr(self._local, 'in_transaction', False):
                        conn.close()
                    return row[0]  # Return existing ID
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
                    
        self._close(conn)
        
        # Extract graph node
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
        conn = self._connect()
        c = conn.cursor()
        results = []
        
        # 1. Try Vector Semantic Search first if available
        if sqlite_vec is not None:
            emb = self._get_embedding(query)
            if emb:
                try:
                    c.execute("""
                        SELECT a.id, a.mistake, a.root_cause, a.fix, a.severity, a.tags, a.created_at, v.distance
                        FROM anti_patterns_vec v 
                        JOIN anti_patterns a ON v.id = a.id
                        WHERE v.embedding MATCH ? AND k = ?
                        ORDER BY v.distance
                    """, (sqlite_vec.serialize_float32(emb), limit))
                    results = [{"id": r[0], "mistake": r[1], "root_cause": r[2], "fix": r[3],
                                 "severity": r[4], "tags": r[5], "created_at": r[6]} for r in c.fetchall()]
                except Exception as e:
                    pass
        
        # 2. Fallback to FTS text match if vector search yielded nothing
        if not results:
            try:
                c.execute("""
                    SELECT a.id, a.mistake, a.root_cause, a.fix, a.severity, a.tags, a.created_at
                    FROM anti_patterns_fts f JOIN anti_patterns a ON f.rowid = a.id
                    WHERE anti_patterns_fts MATCH ? ORDER BY rank LIMIT ?
                """, (self._sanitize_fts_query(query), limit))
                results = [{"id": r[0], "mistake": r[1], "root_cause": r[2], "fix": r[3],
                             "severity": r[4], "tags": r[5], "created_at": r[6]} for r in c.fetchall()]
            except Exception:
                pass
                
        if not getattr(self._local, 'in_transaction', False):
            conn.close()
        return results

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
            conn.close()
        return results

    def count_anti_patterns(self) -> int:
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM anti_patterns")
        count = c.fetchone()[0]
        if not getattr(self._local, 'in_transaction', False):
            conn.close()
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
        conn = self._connect()
        c = conn.cursor()
        results = []
        
        # 1. Try Vector Semantic Search first
        if sqlite_vec is not None:
            emb = self._get_embedding(query)
            if emb:
                try:
                    c.execute("""
                        SELECT d.id, d.decision, d.rationale, d.alternatives_rejected, d.context, d.created_at, v.distance
                        FROM decisions_vec v 
                        JOIN decisions d ON v.id = d.id
                        WHERE v.embedding MATCH ? AND k = ?
                        ORDER BY v.distance
                    """, (sqlite_vec.serialize_float32(emb), limit))
                    results = [{"id": r[0], "decision": r[1], "rationale": r[2],
                                 "alternatives_rejected": r[3], "context": r[4], "created_at": r[5]} for r in c.fetchall()]
                except Exception:
                    pass
        
        # 2. Fallback to FTS
        if not results:
            try:
                c.execute("""
                    SELECT d.id, d.decision, d.rationale, d.alternatives_rejected, d.context, d.created_at
                    FROM decisions_fts f JOIN decisions d ON f.rowid = d.id
                    WHERE decisions_fts MATCH ? ORDER BY rank LIMIT ?
                """, (self._sanitize_fts_query(query), limit))
                results = [{"id": r[0], "decision": r[1], "rationale": r[2],
                             "alternatives_rejected": r[3], "context": r[4], "created_at": r[5]} for r in c.fetchall()]
            except Exception:
                results = []
        if not getattr(self._local, 'in_transaction', False):
            conn.close()
        return results

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
            conn.close()
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
            conn.close()
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
            conn.close()
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
            conn.close()
        return metrics

    # ==================== GOALS (OKR) ====================

    def set_goal(self, objective: str, key_results: list[str]) -> int:
        import hashlib
        conn = self._connect()
        c = conn.cursor()
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        progress = {kr: 0 for kr in key_results}
        # Dedup: check if an active goal with the same objective already exists
        dedup_hash = hashlib.sha256(objective.strip().lower().encode()).hexdigest()[:16]
        c.execute("SELECT id FROM goals WHERE status = 'active' AND objective = ?", (objective,))
        existing = c.fetchone()
        if existing:
            if not getattr(self._local, 'in_transaction', False):
                conn.close()
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
                conn.close()
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
            conn.close()
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
            conn.close()
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
            conn.close()
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
            conn.close()

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
            conn.close()
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
            conn.close()
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
        """Record something the system should have caught but didn't."""
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
            conn.close()
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
        results = [{"id": r[0], "name": r[1], "trigger": r[2], "check": r[3],
                     "action": r[4], "severity": r[5], "triggered": r[6]}
                    for r in c.fetchall()]
        if not getattr(self._local, 'in_transaction', False):
            conn.close()
        return results

    def increment_rule_trigger(self, rule_id: int) -> None:
        """Increment the trigger count for a prevention rule."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("UPDATE prevention_rules SET times_triggered = times_triggered + 1 WHERE id = ?",
                  (rule_id,))
        self._close(conn)

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
        never_triggered = [r for r in rules if r['triggered'] == 0]
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
            conn.close()
        
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
            conn.close()
        
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
            conn.close()
        
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

