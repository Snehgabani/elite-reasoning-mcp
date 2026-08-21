"""Persistent SQLite store for LOOP BY SG MCP.

Stores reasoning sessions, metrics, memory items, calibration data,
and evaluation results. Thread-safe with connection pooling.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class SingularityStore:
    """Thread-safe SQLite persistence layer with WAL mode and JSON storage."""

    def __init__(self, brain_dir: str):
        self._brain_dir = Path(brain_dir)
        self._brain_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._brain_dir / "singularity.db"
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _conn(self):
        with self._lock:
            conn = sqlite3.connect(str(self._db_path), timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS reasoning_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    prompt TEXT NOT NULL,
                    intent TEXT DEFAULT 'general',
                    complexity INTEGER DEFAULT 1,
                    budget_tier TEXT DEFAULT 'standard',
                    steps_json TEXT DEFAULT '[]',
                    outcome_json TEXT DEFAULT '{}',
                    metrics_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    duration_ms INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS memory_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_type TEXT NOT NULL DEFAULT 'fact',
                    content TEXT NOT NULL,
                    scope TEXT NOT NULL DEFAULT 'global',
                    source TEXT DEFAULT 'explicit',
                    trust_score REAL DEFAULT 0.7,
                    privacy_class TEXT DEFAULT 'internal',
                    tags TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    accessed_at TEXT,
                    access_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS anti_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mistake TEXT NOT NULL,
                    root_cause TEXT DEFAULT '',
                    fix TEXT DEFAULT '',
                    severity TEXT DEFAULT 'medium',
                    tags TEXT DEFAULT '',
                    hit_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_hit_at TEXT
                );

                CREATE TABLE IF NOT EXISTS calibration_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prediction_id TEXT UNIQUE NOT NULL,
                    claim TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    domain TEXT DEFAULT 'general',
                    outcome TEXT,
                    correct INTEGER,
                    resolved_at TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS eval_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    eval_name TEXT NOT NULL,
                    variant TEXT NOT NULL DEFAULT 'baseline',
                    prompt TEXT NOT NULL,
                    output TEXT DEFAULT '',
                    score REAL DEFAULT 0.0,
                    metrics_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tool_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT NOT NULL,
                    args_summary TEXT DEFAULT '',
                    result_summary TEXT DEFAULT '',
                    duration_ms INTEGER DEFAULT 0,
                    session_id TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision TEXT NOT NULL,
                    rationale TEXT DEFAULT '',
                    alternatives TEXT DEFAULT '',
                    context TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS quality_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    score REAL NOT NULL,
                    dimension TEXT NOT NULL,
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS metrics_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT DEFAULT '',
                    tags_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_items(memory_type);
                CREATE INDEX IF NOT EXISTS idx_memory_scope ON memory_items(scope);
                CREATE INDEX IF NOT EXISTS idx_anti_severity ON anti_patterns(severity);
                CREATE INDEX IF NOT EXISTS idx_eval_name ON eval_results(eval_name);
                CREATE INDEX IF NOT EXISTS idx_tool_name ON tool_usage(tool_name);
                CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics_snapshots(metric_name);
                CREATE INDEX IF NOT EXISTS idx_sessions_created ON reasoning_sessions(created_at);
            """)

    # ── Reasoning Sessions ──────────────────────────────────

    def create_session(self, session_id: str, prompt: str, intent: str,
                       complexity: int, budget_tier: str, steps: list[dict]) -> int:
        with self._conn() as conn:
            # BUGFIX (telemetry flood guard): a runaway benchmark loop once wrote
            # ~749k sessions in 2.5h (avg ~5,000/min, 350MB DB). Real usage is
            # << 1/min, so cap session creation at 600/min — beyond that, drop
            # the record (reporting stays correct; no crash, no bloat).
            recent = conn.execute(
                "SELECT COUNT(*) FROM reasoning_sessions WHERE created_at > "
                "datetime('now', '-60 seconds')"
            ).fetchone()[0]
            if recent >= 600:
                return 0
            cur = conn.execute(
                "INSERT INTO reasoning_sessions (session_id, prompt, intent, complexity, budget_tier, steps_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, prompt, intent, complexity, budget_tier,
                 json.dumps(steps), self._utc_now())
            )
            return cur.lastrowid

    def complete_session(self, session_id: str, outcome: dict, metrics: dict, duration_ms: int):
        with self._conn() as conn:
            conn.execute(
                "UPDATE reasoning_sessions SET outcome_json=?, metrics_json=?, duration_ms=?, completed_at=? "
                "WHERE session_id=?",
                (json.dumps(outcome), json.dumps(metrics), duration_ms, self._utc_now(), session_id)
            )

    def get_session(self, session_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM reasoning_sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            if row:
                return dict(row)
        return None

    def get_recent_sessions(self, limit: int = 20) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM reasoning_sessions ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Memory ──────────────────────────────────────────────

    def remember(self, memory_type: str, content: str, scope: str = "global",
                 source: str = "explicit", trust_score: float = 0.7,
                 privacy_class: str = "internal", tags: str = "") -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO memory_items (memory_type, content, scope, source, trust_score, privacy_class, tags, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (memory_type, content, scope, source, trust_score, privacy_class, tags, self._utc_now())
            )
            return cur.lastrowid

    def search_memory(self, query: str, scope: str = "", limit: int = 10,
                      min_trust: float = 0.3) -> list[dict]:
        with self._conn() as conn:
            terms = query.lower().split()
            conditions = ["trust_score >= ?", "privacy_class != 'secret'"]
            params: list[Any] = [min_trust]
            if scope:
                conditions.append("scope = ?")
                params.append(scope)
            # FTS-like keyword matching
            for term in terms[:5]:
                conditions.append("(LOWER(content) LIKE ? OR LOWER(tags) LIKE ?)")
                params.extend([f"%{term}%", f"%{term}%"])
            sql = f"SELECT * FROM memory_items WHERE {' AND '.join(conditions)} ORDER BY trust_score DESC, access_count DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            results = [dict(r) for r in rows]
            # Update access tracking
            for r in results:
                conn.execute(
                    "UPDATE memory_items SET access_count = access_count + 1, accessed_at = ? WHERE id = ?",
                    (self._utc_now(), r['id'])
                )
            return results

    def forget_memory(self, memory_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM memory_items WHERE id=?", (memory_id,))
            return cur.rowcount > 0

    def get_memory_stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
            by_type = conn.execute(
                "SELECT memory_type, COUNT(*) as cnt FROM memory_items GROUP BY memory_type"
            ).fetchall()
            avg_trust = conn.execute("SELECT AVG(trust_score) FROM memory_items").fetchone()[0] or 0
            return {
                "total_items": total,
                "by_type": {r[0]: r[1] for r in by_type},
                "avg_trust": round(avg_trust, 3),
            }

    # ── Anti-Patterns ──────────────────────────────────────

    def record_anti_pattern(self, mistake: str, root_cause: str, fix: str,
                            severity: str = "medium", tags: str = "") -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO anti_patterns (mistake, root_cause, fix, severity, tags, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (mistake, root_cause, fix, severity, tags, self._utc_now())
            )
            return cur.lastrowid

    def check_anti_patterns(self, query: str, limit: int = 5) -> list[dict]:
        with self._conn() as conn:
            terms = query.lower().split()
            conditions = []
            params: list[Any] = []
            for term in terms[:5]:
                if len(term) > 2:
                    conditions.append(
                        "(LOWER(mistake) LIKE ? OR LOWER(root_cause) LIKE ? OR LOWER(fix) LIKE ? OR LOWER(tags) LIKE ?)"
                    )
                    params.extend([f"%{term}%"] * 4)
            if not conditions:
                return []
            sql = f"SELECT * FROM anti_patterns WHERE {' OR '.join(conditions)} ORDER BY severity DESC, hit_count DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            results = [dict(r) for r in rows]
            for r in results:
                conn.execute(
                    "UPDATE anti_patterns SET hit_count = hit_count + 1, last_hit_at = ? WHERE id = ?",
                    (self._utc_now(), r['id'])
                )
            return results

    def get_all_anti_patterns(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM anti_patterns ORDER BY severity DESC, hit_count DESC").fetchall()
            return [dict(r) for r in rows]

    # ── Calibration ─────────────────────────────────────────

    def log_calibration(self, prediction_id: str, claim: str, confidence: float, domain: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO calibration_predictions (prediction_id, claim, confidence, domain, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (prediction_id, claim, confidence, domain, self._utc_now())
            )

    def resolve_calibration(self, prediction_id: str, outcome: str, correct: bool) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE calibration_predictions SET outcome=?, correct=?, resolved_at=? WHERE prediction_id=?",
                (outcome, 1 if correct else 0, self._utc_now(), prediction_id)
            )
            return cur.rowcount > 0

    def get_calibration_score(self, domain: str | None = None, days: int = 30) -> dict:
        with self._conn() as conn:
            cutoff = self._utc_offset(days)
            conditions = ["resolved_at IS NOT NULL", "created_at > ?"]
            params: list[Any] = [cutoff]
            if domain:
                conditions.append("domain = ?")
                params.append(domain)
            sql = f"SELECT confidence, correct FROM calibration_predictions WHERE {' AND '.join(conditions)}"
            rows = conn.execute(sql, params).fetchall()
            if not rows:
                return {"total_predictions": 0, "brier_score": None, "accuracy": None,
                        "avg_confidence": None, "calibration_status": "no_data"}
            confidences = [r[0] for r in rows]
            outcomes = [r[1] for r in rows]
            n = len(rows)
            brier = sum((c - o) ** 2 for c, o in zip(confidences, outcomes)) / n
            accuracy = sum(outcomes) / n
            avg_conf = sum(confidences) / n
            # Calibration buckets (v15 P1 fix: track BOTH confidence and outcome
            # per bucket so ECE = |bucket accuracy − bucket mean confidence|).
            buckets = {"0-20%": [], "20-40%": [], "40-60%": [], "60-80%": [], "80-100%": []}
            for c, o in zip(confidences, outcomes):
                if c < 0.2: buckets["0-20%"].append((c, o))
                elif c < 0.4: buckets["20-40%"].append((c, o))
                elif c < 0.6: buckets["40-60%"].append((c, o))
                elif c < 0.8: buckets["60-80%"].append((c, o))
                else: buckets["80-100%"].append((c, o))
            table = []
            for name, pairs in buckets.items():
                if pairs:
                    acc = sum(1 for _, o in pairs if o) / len(pairs)
                    conf = sum(c for c, _ in pairs) / len(pairs)
                    table.append({
                        "bucket": name, "count": len(pairs),
                        "expected": round(conf, 3),
                        "actual": round(acc, 3),
                    })
            # BUGFIX: status labels are meaningless below a minimum sample size —
            # n=2 "well_calibrated" is statistically void. Require >= 10 resolved
            # predictions before emitting a calibration verdict.
            if n < 10:
                status = "insufficient_data"
            else:
                status = "well_calibrated" if brier < 0.1 else "overconfident" if avg_conf > accuracy + 0.1 else "underconfident" if avg_conf < accuracy - 0.1 else "fair"
            # v15 P1: ECE — weighted mean |bucket accuracy − bucket confidence|
            # (Naeini et al. 2015 standard). Requires >= 1 populated bucket.
            if table:
                ece = sum(
                    b["count"] * abs(b["actual"] - b["expected"])
                    for b in table
                ) / n
            else:
                ece = None
            return {
                "total_predictions": n,
                "brier_score": round(brier, 4),
                "ece_score": round(ece, 4) if ece is not None else None,
                "accuracy": round(accuracy, 4),
                "avg_confidence": round(avg_conf, 4),
                "calibration_status": status,
                "calibration_table": table,
            }

    # ── Eval Results ────────────────────────────────────────

    def record_eval(self, eval_name: str, variant: str, prompt: str,
                    output: str, score: float, metrics: dict):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO eval_results (eval_name, variant, prompt, output, score, metrics_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (eval_name, variant, prompt, output, score, json.dumps(metrics), self._utc_now())
            )

    def get_eval_comparison(self, eval_name: str, days: int = 30) -> dict:
        with self._conn() as conn:
            cutoff = self._utc_offset(days)
            rows = conn.execute(
                "SELECT variant, score, metrics_json FROM eval_results WHERE eval_name=? AND created_at > ?",
                (eval_name, cutoff)
            ).fetchall()
            if not rows:
                return {"eval_name": eval_name, "variants": {}, "comparison": "no_data"}
            variants: dict[str, list[float]] = {}
            for r in rows:
                v = r[0]
                if v not in variants:
                    variants[v] = []
                variants[v].append(r[1])
            summary = {}
            for v, scores in variants.items():
                summary[v] = {
                    "count": len(scores),
                    "mean": round(sum(scores) / len(scores), 4),
                    "min": round(min(scores), 4),
                    "max": round(max(scores), 4),
                    "stddev": round(self._stddev(scores), 4),
                }
            comparison = "no_comparison"
            if "enhanced" in summary and "baseline" in summary:
                delta = summary["enhanced"]["mean"] - summary["baseline"]["mean"]
                comparison = f"enhanced_{'better' if delta > 0 else 'worse'}_by_{abs(delta):.4f}"
            return {"eval_name": eval_name, "variants": summary, "comparison": comparison}

    # ── Tool Usage ──────────────────────────────────────────

    def log_tool_usage(self, tool_name: str, args_summary: str, result_summary: str,
                       session_id: str, duration_ms: int):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO tool_usage (tool_name, args_summary, result_summary, duration_ms, session_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (tool_name, args_summary[:500], result_summary[:500], duration_ms, session_id, self._utc_now())
            )

    def get_tool_usage_stats(self, days: int = 7) -> dict:
        with self._conn() as conn:
            cutoff = self._utc_offset(days)
            rows = conn.execute(
                "SELECT tool_name, COUNT(*) as cnt, AVG(duration_ms) as avg_ms, "
                "SUM(duration_ms) as total_ms FROM tool_usage WHERE created_at > ? "
                "GROUP BY tool_name ORDER BY cnt DESC",
                (cutoff,)
            ).fetchall()
            return {
                "period_days": days,
                "tools": [
                    {"name": r[0], "calls": r[1], "avg_ms": round(r[2] or 0, 1), "total_ms": r[3] or 0}
                    for r in rows
                ],
                "total_calls": sum(r[1] for r in rows),
                "total_ms": sum(r[3] or 0 for r in rows),
            }

    # ── Decisions ───────────────────────────────────────────

    def record_decision(self, decision: str, rationale: str = "",
                        alternatives: str = "", context: str = "") -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO decisions (decision, rationale, alternatives, context, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (decision, rationale, alternatives, context, self._utc_now())
            )
            return cur.lastrowid

    def search_decisions(self, query: str, limit: int = 10) -> list[dict]:
        with self._conn() as conn:
            terms = query.lower().split()
            conditions = []
            params: list[Any] = []
            for term in terms[:5]:
                if len(term) > 2:
                    conditions.append("(LOWER(decision) LIKE ? OR LOWER(rationale) LIKE ?)")
                    params.extend([f"%{term}%", f"%{term}%"])
            if not conditions:
                rows = conn.execute("SELECT * FROM decisions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            else:
                sql = f"SELECT * FROM decisions WHERE {' OR '.join(conditions)} ORDER BY created_at DESC LIMIT ?"
                params.append(limit)
                rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    # ── Quality Scores ──────────────────────────────────────

    def record_quality_score(self, score: float, dimension: str, notes: str = ""):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO quality_scores (score, dimension, notes, created_at) VALUES (?, ?, ?, ?)",
                (score, dimension, notes, self._utc_now())
            )

    def get_quality_trend(self, dimension: str = "", days: int = 30) -> dict:
        with self._conn() as conn:
            cutoff = self._utc_offset(days)
            conditions = ["created_at > ?"]
            params: list[Any] = [cutoff]
            if dimension:
                conditions.append("dimension = ?")
                params.append(dimension)
            sql = f"SELECT score, dimension, created_at FROM quality_scores WHERE {' AND '.join(conditions)} ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            if not rows:
                return {"trend": "no_data", "count": 0}
            scores = [r[0] for r in rows]
            n = len(scores)
            avg = sum(scores) / n
            # Simple trend: compare first half vs second half
            mid = n // 2
            if mid > 0:
                first_half = sum(scores[mid:]) / (n - mid)
                second_half = sum(scores[:mid]) / mid
                if second_half > first_half + 5:
                    trend = "improving"
                elif second_half < first_half - 5:
                    trend = "declining"
                else:
                    trend = "stable"
            else:
                trend = "insufficient_data"
            return {
                "trend": trend,
                "count": n,
                "average": round(avg, 2),
                "min": round(min(scores), 2),
                "max": round(max(scores), 2),
                "recent": [
                    {"score": r[0], "dimension": r[1], "date": r[2]}
                    for r in rows[:10]
                ],
            }

    def get_quality_variance(self, dimension: str = "", days: int = 30) -> dict:
        """Variance-aware diagnostics (v15 P0 #4, ACL 2026 tutorial:
        consistency across seeds/runs, not just point accuracy; 'Stop Using
        Temperature 0 for LLM Evals' — temp 0 hides variance). Computes
        dispersion of recorded quality scores: std, CV, stability grade."""
        with self._conn() as conn:
            cutoff = self._utc_offset(days)
            conditions = ["created_at > ?"]
            params: list[Any] = [cutoff]
            if dimension:
                conditions.append("dimension = ?")
                params.append(dimension)
            sql = f"SELECT score, dimension, created_at FROM quality_scores WHERE {' AND '.join(conditions)} ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            if not rows:
                return {"trend": "no_data", "count": 0}
            scores = [r[0] for r in rows]
            n = len(scores)
            mean = sum(scores) / n
            var = sum((s - mean) ** 2 for s in scores) / n
            std = var ** 0.5
            cv = (std / mean) if mean else 0.0
            if cv < 0.05:
                grade = "stable"
            elif cv < 0.15:
                grade = "moderate"
            else:
                grade = "volatile"
            return {
                "trend": "variance",
                "count": n,
                "mean": round(mean, 4),
                "std": round(std, 4),
                "cv": round(cv, 4),
                "min": round(min(scores), 4),
                "max": round(max(scores), 4),
                "range": round(max(scores) - min(scores), 4),
                "stability_grade": grade,
                "interpretation": (
                    f"Quality dispersion over {n} runs: mean {mean:.3f} ± "
                    f"{std:.3f} (CV {cv:.1%}) → {grade}. "
                    f"{'Consistent across runs.' if grade == 'stable' else 'Spread signals seed/run sensitivity — triangulate before trusting point estimates.'}"
                ),
            }

    # ── Metrics Snapshots ───────────────────────────────────

    def record_metric(self, name: str, value: float, unit: str = "", tags: dict | None = None):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO metrics_snapshots (metric_name, value, unit, tags_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, value, unit, json.dumps(tags or {}), self._utc_now())
            )

    def get_metric_trend(self, name: str, days: int = 30) -> dict:
        with self._conn() as conn:
            cutoff = self._utc_offset(days)
            rows = conn.execute(
                "SELECT value, unit, created_at FROM metrics_snapshots WHERE metric_name=? AND created_at > ? ORDER BY created_at",
                (name, cutoff)
            ).fetchall()
            if not rows:
                return {"metric": name, "trend": "no_data", "count": 0}
            values = [r[0] for r in rows]
            n = len(values)
            return {
                "metric": name,
                "count": n,
                "latest": values[-1],
                "average": round(sum(values) / n, 4),
                "min": min(values),
                "max": max(values),
                "unit": rows[0][1],
                "trend": self._compute_trend(values),
            }

    # ── Operational Summary ─────────────────────────────────

    def get_operational_summary(self, days: int = 7) -> dict:
        with self._conn() as conn:
            cutoff = self._utc_offset(days)
            sessions = conn.execute(
                "SELECT COUNT(*), AVG(duration_ms) FROM reasoning_sessions WHERE created_at > ?",
                (cutoff,)
            ).fetchone()
            tool_calls = conn.execute(
                "SELECT COUNT(*), AVG(duration_ms) FROM tool_usage WHERE created_at > ?",
                (cutoff,)
            ).fetchone()
            memory = conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
            patterns = conn.execute("SELECT COUNT(*) FROM anti_patterns").fetchone()[0]
            decisions = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
            return {
                "period_days": days,
                "sessions": {"count": sessions[0] or 0, "avg_duration_ms": round(sessions[1] or 0, 1)},
                "tool_calls": {"count": tool_calls[0] or 0, "avg_duration_ms": round(tool_calls[1] or 0, 1)},
                "memory_items": memory,
                "anti_patterns": patterns,
                "decisions": decisions,
            }

    # ── Helpers ─────────────────────────────────────────────

    @staticmethod
    def _utc_now() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

    @staticmethod
    def _utc_offset(days: int) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() - days * 86400))

    @staticmethod
    def _stddev(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return variance ** 0.5

    @staticmethod
    def _compute_trend(values: list[float]) -> str:
        if len(values) < 3:
            return "insufficient_data"
        mid = len(values) // 2
        first = sum(values[:mid]) / mid
        second = sum(values[mid:]) / (len(values) - mid)
        if second > first * 1.05:
            return "improving"
        elif second < first * 0.95:
            return "declining"
        return "stable"
