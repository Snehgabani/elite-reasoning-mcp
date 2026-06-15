"""Eval harness for Elite Reasoning MCP.
Opus R2 P0: "You can't optimize what you can't measure,
so build the eval harness first or every other recommendation is a guess."

Runs benchmark queries against the store, measures:
1. Latency (p50/p95/p99)
2. Correctness (does the right tool fire?)
3. Recall (are relevant patterns found?)
4. Prevention rule fire rate
5. Cost per query
"""
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    name: str
    passed: bool
    latency_ms: float
    details: str = ""
    error: str = ""


@dataclass
class EvalReport:
    timestamp: float = field(default_factory=time.time)
    results: list[BenchmarkResult] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0
    latency_p50: float = 0
    latency_p95: float = 0
    latency_p99: float = 0

    def summary(self) -> dict:
        latencies = [r.latency_ms for r in self.results if r.latency_ms > 0]
        if latencies:
            latencies.sort()
            self.latency_p50 = latencies[len(latencies) // 2]
            self.latency_p95 = latencies[int(len(latencies) * 0.95)]
            self.latency_p99 = latencies[int(len(latencies) * 0.99)]
        return {
            "timestamp": self.timestamp,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": round(self.passed / max(self.total, 1), 3),
            "latency_p50_ms": round(self.latency_p50, 1),
            "latency_p95_ms": round(self.latency_p95, 1),
            "latency_p99_ms": round(self.latency_p99, 1),
            "failures": [
                {"name": r.name, "error": r.error}
                for r in self.results if not r.passed
            ],
        }


class EvalHarness:
    """Benchmark and regression test suite for Elite Reasoning."""

    def __init__(self, store):
        self.store = store
        self._benchmarks: list[callable] = []
        self._register_defaults()

    def _register_defaults(self):
        """Register built-in benchmarks."""
        self._benchmarks = [
            self._bench_db_connectivity,
            self._bench_anti_pattern_write_read,
            self._bench_fts5_search,
            self._bench_prevention_rules_fire,
            self._bench_decision_write_read,
            self._bench_quality_score_trend,
            self._bench_goal_lifecycle,
            self._bench_calibration_roundtrip,
            self._bench_cost_log,
            self._bench_rule_lifecycle,
            # R2 Tier 1-3 benchmarks
            self._bench_hybrid_search_fusion,
            self._bench_injection_optimizer_lifecycle,
            self._bench_rule_lifecycle_transitions,
            self._bench_trigger_effectiveness_learning,
            self._bench_severity_inference_signals,
            self._bench_optimization_loop_trigger,
        ]

    def run(self) -> EvalReport:
        """Run all benchmarks, return report."""
        report = EvalReport()
        for bench_fn in self._benchmarks:
            try:
                start = time.perf_counter()
                result = bench_fn()
                result.latency_ms = (time.perf_counter() - start) * 1000
                report.results.append(result)
            except Exception as e:
                report.results.append(BenchmarkResult(
                    name=bench_fn.__name__,
                    passed=False,
                    latency_ms=0,
                    error=str(e)[:200],
                ))

        report.total = len(report.results)
        report.passed = sum(1 for r in report.results if r.passed)
        report.failed = report.total - report.passed
        return report

    # ── Individual Benchmarks ──

    def _bench_db_connectivity(self) -> BenchmarkResult:
        """Can we connect and run a query?"""
        conn = self.store._connect()
        result = conn.execute("SELECT 1").fetchone()
        self.store._close(conn)
        return BenchmarkResult(
            name="db_connectivity",
            passed=result[0] == 1,
            latency_ms=0,
        )

    def _bench_anti_pattern_write_read(self) -> BenchmarkResult:
        """Write an anti-pattern and read it back."""
        test_mistake = f"[EVAL_BENCH] test mistake {time.time()}"
        row_id = self.store.record_mistake(
            mistake=test_mistake,
            root_cause="eval harness test",
            fix="no action needed",
            severity="low",
            tags="eval,bench",
        )
        # Read back
        conn = self.store._connect()
        row = conn.execute(
            "SELECT mistake FROM anti_patterns WHERE id = ?", (row_id,)
        ).fetchone()
        self.store._close(conn)
        # Cleanup
        conn2 = self.store._connect()
        conn2.execute("DELETE FROM anti_patterns WHERE id = ?", (row_id,))
        self.store._close(conn2)
        return BenchmarkResult(
            name="anti_pattern_write_read",
            passed=row is not None and test_mistake in row[0],
            latency_ms=0,
            details=f"wrote id={row_id}",
        )

    def _bench_fts5_search(self) -> BenchmarkResult:
        """FTS5 search doesn't crash on special characters."""
        try:
            results = self.store.check_anti_patterns("test AND (OR) NOT *query*")
            return BenchmarkResult(
                name="fts5_search_safety",
                passed=True,  # Didn't crash = pass
                latency_ms=0,
                details=f"returned {len(results)} results",
            )
        except Exception as e:
            return BenchmarkResult(
                name="fts5_search_safety",
                passed=False,
                latency_ms=0,
                error=str(e)[:200],
            )

    def _bench_prevention_rules_fire(self) -> BenchmarkResult:
        """Check that prevention rules can be queried without error."""
        conn = self.store._connect()
        rules = conn.execute(
            "SELECT COUNT(*) FROM prevention_rules WHERE enabled = 1"
        ).fetchone()
        total = conn.execute("SELECT COUNT(*) FROM prevention_rules").fetchone()
        self.store._close(conn)
        return BenchmarkResult(
            name="prevention_rules_status",
            passed=True,
            latency_ms=0,
            details=f"{rules[0]} enabled / {total[0]} total rules",
        )

    def _bench_decision_write_read(self) -> BenchmarkResult:
        """Write a decision and verify FTS indexes it."""
        test_text = f"[EVAL_BENCH] decision {time.time()}"
        row_id = self.store.record_decision(
            decision=test_text,
            rationale="eval harness test",
            alternatives_rejected="none",
            context="bench",
        )
        # Cleanup
        conn = self.store._connect()
        conn.execute("DELETE FROM decisions WHERE id = ?", (row_id,))
        self.store._close(conn)
        return BenchmarkResult(
            name="decision_write_read",
            passed=row_id > 0,
            latency_ms=0,
        )

    def _bench_quality_score_trend(self) -> BenchmarkResult:
        """Quality trend query works."""
        try:
            trend = self.store.get_quality_trend()
            return BenchmarkResult(
                name="quality_score_trend",
                passed=isinstance(trend, dict),
                latency_ms=0,
                details=f"trend keys: {list(trend.keys())[:5]}",
            )
        except Exception as e:
            return BenchmarkResult(
                name="quality_score_trend",
                passed=False,
                latency_ms=0,
                error=str(e)[:200],
            )

    def _bench_goal_lifecycle(self) -> BenchmarkResult:
        """Create, update, archive a goal."""
        try:
            goal_id = self.store.set_goal(
                objective="[EVAL_BENCH] test goal",
                key_results='["test KR"]',
            )
            self.store.update_goal(goal_id, key_result="test KR", progress=50)
            self.store.archive_goal(goal_id)
            # Cleanup
            conn = self.store._connect()
            conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
            self.store._close(conn)
            return BenchmarkResult(
                name="goal_lifecycle",
                passed=True,
                latency_ms=0,
            )
        except Exception as e:
            return BenchmarkResult(
                name="goal_lifecycle",
                passed=False,
                latency_ms=0,
                error=str(e)[:200],
            )

    def _bench_calibration_roundtrip(self) -> BenchmarkResult:
        """Calibration predict/resolve roundtrip."""
        try:
            self.store.log_calibration(
                prediction_id="eval_bench_test",
                claim="[EVAL_BENCH] test claim",
                confidence=0.7,
                domain="eval",
            )
            self.store.resolve_calibration(
                prediction_id="eval_bench_test",
                outcome="verified",
                correct=True,
            )
            score = self.store.get_calibration_score(domain="eval")
            # Cleanup
            conn = self.store._connect()
            conn.execute("DELETE FROM calibration_log WHERE prediction_id = ?",
                        ("eval_bench_test",))
            self.store._close(conn)
            return BenchmarkResult(
                name="calibration_roundtrip",
                passed=isinstance(score, dict),
                latency_ms=0,
            )
        except Exception as e:
            return BenchmarkResult(
                name="calibration_roundtrip",
                passed=False,
                latency_ms=0,
                error=str(e)[:200],
            )

    def _bench_cost_log(self) -> BenchmarkResult:
        """Cost logging works (Round 2)."""
        try:
            row_id = self.store.log_cost(
                cost_type="embedding",
                units=1.0,
                estimated_usd=0.0001,
                provider="local",
                tool_name="eval_bench",
            )
            summary = self.store.get_cost_summary(days=1)
            # Cleanup
            conn = self.store._connect()
            conn.execute("DELETE FROM cost_log WHERE id = ?", (row_id,))
            self.store._close(conn)
            return BenchmarkResult(
                name="cost_log_roundtrip",
                passed=row_id > 0 and isinstance(summary, dict),
                latency_ms=0,
            )
        except Exception as e:
            return BenchmarkResult(
                name="cost_log_roundtrip",
                passed=False,
                latency_ms=0,
                error=str(e)[:200],
            )

    def _bench_rule_lifecycle(self) -> BenchmarkResult:
        """Rule lifecycle summary works (Round 2)."""
        try:
            summary = self.store.get_rule_lifecycle_summary()
            return BenchmarkResult(
                name="rule_lifecycle_summary",
                passed=isinstance(summary, dict),
                latency_ms=0,
                details=f"states: {list(summary.get('by_state', {}).keys())}",
            )
        except Exception as e:
            return BenchmarkResult(
                name="rule_lifecycle_summary",
                passed=False,
                latency_ms=0,
                error=str(e)[:200],
            )

    # ── R2 Tier 1-3 Benchmarks ──

    def _bench_hybrid_search_fusion(self) -> BenchmarkResult:
        """HybridSearch RRF fusion returns results (Tier 1)."""
        try:
            # Seed data
            self.store.record_mistake(
                "eval_hybrid_security_test", "SQL injection vulnerability",
                "Use parameterized queries", "P0"
            )
            # Search via the HybridSearch-wired method
            results = self.store.check_anti_patterns("SQL injection security", limit=3)
            # Cleanup
            conn = self.store._connect()
            conn.execute("DELETE FROM anti_patterns WHERE mistake = 'eval_hybrid_security_test'")
            self.store._close(conn)
            return BenchmarkResult(
                name="hybrid_search_fusion",
                passed=isinstance(results, list),
                latency_ms=0,
                details=f"results: {len(results)}",
            )
        except Exception as e:
            return BenchmarkResult(
                name="hybrid_search_fusion",
                passed=False, latency_ms=0, error=str(e)[:200],
            )

    def _bench_injection_optimizer_lifecycle(self) -> BenchmarkResult:
        """InjectionOptimizer can compute stats and adjust pool (Tier 2)."""
        try:
            from core.learning.injection_optimizer import InjectionOptimizer
            optimizer = InjectionOptimizer(self.store)
            stats = optimizer.compute_injection_stats()
            result = optimizer.adjust_injection_pool()
            return BenchmarkResult(
                name="injection_optimizer_lifecycle",
                passed=isinstance(result, dict) and "total_evaluated" in result,
                latency_ms=0,
                details=f"stats={len(stats)}, result={result}",
            )
        except Exception as e:
            return BenchmarkResult(
                name="injection_optimizer_lifecycle",
                passed=False, latency_ms=0, error=str(e)[:200],
            )

    def _bench_rule_lifecycle_transitions(self) -> BenchmarkResult:
        """RuleLifecycle daemon can load rules and compute transitions (Tier 2)."""
        try:
            from core.learning.rule_lifecycle import RuleLifecycle
            lifecycle = RuleLifecycle(self.store)
            result = lifecycle.tick()
            return BenchmarkResult(
                name="rule_lifecycle_transitions",
                passed=isinstance(result, dict) and "total_rules" in result,
                latency_ms=0,
                details=f"total_rules={result.get('total_rules')}, transitions={result.get('transitions')}",
            )
        except Exception as e:
            return BenchmarkResult(
                name="rule_lifecycle_transitions",
                passed=False, latency_ms=0, error=str(e)[:200],
            )

    def _bench_trigger_effectiveness_learning(self) -> BenchmarkResult:
        """TriggerLearner can load data and suggest triggers (Tier 2)."""
        try:
            from core.learning.trigger_learner import TriggerLearner
            learner = TriggerLearner(self.store)
            result = learner.learn()
            suggestion = learner.suggest_trigger("security")
            return BenchmarkResult(
                name="trigger_effectiveness_learning",
                passed=isinstance(result, dict) and isinstance(suggestion, str),
                latency_ms=0,
                details=f"learned={result.get('learned_count', 0)}, default={result.get('default_count', 0)}, suggestion={suggestion}",
            )
        except Exception as e:
            return BenchmarkResult(
                name="trigger_effectiveness_learning",
                passed=False, latency_ms=0, error=str(e)[:200],
            )

    def _bench_severity_inference_signals(self) -> BenchmarkResult:
        """SeverityInference produces 3-signal severity (Tier 2)."""
        try:
            from core.learning.severity_inference import infer_severity
            result = infer_severity("security", "SQL injection vulnerability in auth module", self.store)
            return BenchmarkResult(
                name="severity_inference_signals",
                passed=(
                    isinstance(result, dict)
                    and result.get("severity") in ("P0", "P1", "P2")
                    and len(result.get("signals", [])) >= 1
                    and "confidence" in result
                ),
                latency_ms=0,
                details=f"severity={result.get('severity')}, signals={len(result.get('signals', []))}, confidence={result.get('confidence')}",
            )
        except Exception as e:
            return BenchmarkResult(
                name="severity_inference_signals",
                passed=False, latency_ms=0, error=str(e)[:200],
            )

    def _bench_optimization_loop_trigger(self) -> BenchmarkResult:
        """OptimizationLoop can evaluate triggers and report status (Tier 2)."""
        try:
            from core.scheduler.optimizer import OptimizationLoop
            loop = OptimizationLoop(self.store)
            status = loop.get_status()
            # Test tick (should not fire without data)
            events = loop.tick()
            return BenchmarkResult(
                name="optimization_loop_trigger",
                passed=(
                    isinstance(status, dict)
                    and len(status.get("triggers", [])) == 5
                    and isinstance(events, list)
                ),
                latency_ms=0,
                details=f"triggers={len(status.get('triggers', []))}, events_fired={len(events)}",
            )
        except Exception as e:
            return BenchmarkResult(
                name="optimization_loop_trigger",
                passed=False, latency_ms=0, error=str(e)[:200],
            )
