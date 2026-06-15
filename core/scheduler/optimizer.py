"""Optimization Loop — the autonomy controller.

5 triggers that fire when metrics breach thresholds.
Runs as a hook (every Nth tool call) since MCP is request-driven.
Each trigger has an independent cooldown."""
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OptimizationTrigger:
    """A metric-threshold pair that fires an action."""
    name: str
    metric: str
    threshold: float
    direction: str             # "above" or "below"
    window_calls: int
    cooldown_hours: float
    description: str = ""


DEFAULT_TRIGGERS = [
    OptimizationTrigger(
        name="quality_decline",
        metric="quality_score.rolling_avg",
        threshold=70.0, direction="below",
        window_calls=20, cooldown_hours=24,
        description="Quality dropping — run autonomous scan + generate goal",
    ),
    OptimizationTrigger(
        name="injection_ineffective",
        metric="injection.prevention_rate",
        threshold=0.40, direction="below",
        window_calls=50, cooldown_hours=12,
        description="Injection prevention rate falling — adjust pool",
    ),
    OptimizationTrigger(
        name="rule_fp_climbing",
        metric="rules.false_positive_rate",
        threshold=0.30, direction="above",
        window_calls=100, cooldown_hours=6,
        description="Rule false positive rate climbing — lifecycle tick",
    ),
    OptimizationTrigger(
        name="latency_spike",
        metric="latency.p99_ms",
        threshold=2500.0, direction="above",
        window_calls=100, cooldown_hours=2,
        description="Latency p99 over budget — flag slow tools",
    ),
    OptimizationTrigger(
        name="tool_concentration",
        metric="tool_usage.gini_coefficient",
        threshold=0.75, direction="above",
        window_calls=200, cooldown_hours=48,
        description="Tool diversity dropping — boost underused tools",
    ),
]


class OptimizationLoop:
    """Hook-based optimization controller.

    Called every N tool calls (not as a daemon thread) since MCP
    servers are request-driven.

    Usage:
        loop = OptimizationLoop(store)
        events = loop.tick()  # evaluates all triggers, fires if needed
    """

    CHECK_INTERVAL = 10

    def __init__(self, store, triggers: list[OptimizationTrigger] | None = None):
        self.store = store
        self.triggers = triggers or DEFAULT_TRIGGERS
        self._last_fired: dict[str, float] = {}
        self._call_count = 0

    def should_check(self) -> bool:
        """Increment call counter and return True every N calls."""
        self._call_count += 1
        return self._call_count % self.CHECK_INTERVAL == 0

    def tick(self) -> list[dict]:
        """Evaluate all triggers, fire actions for breached thresholds."""
        events = []
        for trigger in self.triggers:
            if self._in_cooldown(trigger):
                continue
            value = self._compute_metric(trigger.metric, trigger.window_calls)
            if value is None:
                continue
            breached = (
                (trigger.direction == "below" and value < trigger.threshold) or
                (trigger.direction == "above" and value > trigger.threshold)
            )
            if breached:
                events.append(self._fire(trigger, value))
        return events

    def _fire(self, trigger: OptimizationTrigger, value: float) -> dict:
        """Execute the action for a breached trigger."""
        logger.warning(
            f"Optimization trigger fired: {trigger.name} "
            f"({trigger.metric}={value:.2f}, threshold={trigger.threshold})"
        )
        event = {
            "trigger": trigger.name, "metric": trigger.metric,
            "value": value, "threshold": trigger.threshold,
            "direction": trigger.direction, "timestamp": time.time(),
            "action_result": None,
        }
        try:
            event["action_result"] = self._execute_action(trigger)
        except Exception as e:
            event["action_result"] = {"error": str(e)}
            logger.error(f"Optimizer action failed for {trigger.name}: {e}")

        self._record_event(trigger, value, event["action_result"])
        self._last_fired[trigger.name] = time.time()
        return event

    def _execute_action(self, trigger: OptimizationTrigger) -> dict:
        """Dispatch to the appropriate action handler."""
        handlers = {
            "quality_decline": self._action_quality_decline,
            "injection_ineffective": self._action_injection_ineffective,
            "rule_fp_climbing": self._action_rule_fp_climbing,
            "latency_spike": self._action_latency_spike,
            "tool_concentration": self._action_tool_concentration,
        }
        handler = handlers.get(trigger.name)
        if handler:
            return handler()
        return {"warning": f"No handler for trigger: {trigger.name}"}

    def _action_quality_decline(self) -> dict:
        try:
            goal_id = self.store.set_goal(
                "[AUTO] Improve quality score above 70 (decline detected)",
                '["Identify top 3 quality issues", "Create prevention rules", "Verify improvement"]'
            )
            return {"action": "goal_created", "goal_id": goal_id}
        except Exception as e:
            return {"action": "goal_creation_failed", "error": str(e)}

    def _action_injection_ineffective(self) -> dict:
        try:
            from core.learning.injection_optimizer import InjectionOptimizer
            return InjectionOptimizer(self.store).adjust_injection_pool()
        except Exception as e:
            return {"error": str(e)}

    def _action_rule_fp_climbing(self) -> dict:
        try:
            from core.learning.rule_lifecycle import RuleLifecycle
            return RuleLifecycle(self.store).tick()
        except Exception as e:
            return {"error": str(e)}

    def _action_latency_spike(self) -> dict:
        conn = self.store._connect()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT tool_name, COUNT(*) as calls,
                       AVG(CAST(json_extract(result_summary, '$.latency_ms') AS REAL)) as avg_ms
                FROM tool_usage_log WHERE created_at > datetime('now', '-1 day')
                GROUP BY tool_name ORDER BY avg_ms DESC LIMIT 5
            """)
            slow = [{"tool": r[0], "calls": r[1], "avg_ms": r[2]}
                    for r in c.fetchall() if r[2] is not None]
            return {"action": "flagged_slow_tools", "tools": slow}
        except Exception as e:
            return {"error": str(e)}
        finally:
            self.store._close(conn)

    def _action_tool_concentration(self) -> dict:
        conn = self.store._connect()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT tool_name, COUNT(*) FROM tool_usage_log
                WHERE created_at > datetime('now', '-7 days')
                GROUP BY tool_name ORDER BY COUNT(*) ASC LIMIT 10
            """)
            return {"action": "identified_underused_tools",
                    "tools": [{"tool": r[0], "calls": r[1]} for r in c.fetchall()]}
        except Exception as e:
            return {"error": str(e)}
        finally:
            self.store._close(conn)

    # ── Metric computation ────────────────────────────────────

    def _compute_metric(self, metric: str, window: int) -> float | None:
        try:
            dispatch = {
                "quality_score.rolling_avg": lambda: self._metric_quality_avg(window),
                "injection.prevention_rate": self._metric_injection_rate,
                "rules.false_positive_rate": self._metric_rule_fp_rate,
                "latency.p99_ms": lambda: self._metric_latency_p99(window),
                "tool_usage.gini_coefficient": lambda: self._metric_gini(window),
            }
            fn = dispatch.get(metric)
            return fn() if fn else None
        except Exception as e:
            logger.debug(f"Metric {metric} failed: {e}")
            return None

    def _metric_quality_avg(self, window: int) -> float | None:
        trend = self.store.get_quality_trend(limit=window)
        scores = trend.get("scores", [])
        if not scores:
            return None
        values = [s["score"] for s in scores if isinstance(s, dict) and "score" in s]
        return sum(values) / len(values) if values else None

    def _metric_injection_rate(self) -> float | None:
        try:
            return self.store.get_injection_prevention_rate().get("prevention_rate")
        except Exception:
            return None

    def _metric_rule_fp_rate(self) -> float | None:
        conn = self.store._connect()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT SUM(COALESCE(false_positive_count, 0)),
                       SUM(COALESCE(true_positive_count, 0))
                FROM prevention_rules WHERE enabled = 1
            """)
            r = c.fetchone()
            if not r or (r[0] + r[1]) == 0:
                return None
            return r[0] / (r[0] + r[1])
        finally:
            self.store._close(conn)

    def _metric_latency_p99(self, window: int) -> float | None:
        conn = self.store._connect()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT CAST(json_extract(result_summary, '$.latency_ms') AS REAL)
                FROM tool_usage_log WHERE created_at > datetime('now', '-1 day')
                AND json_extract(result_summary, '$.latency_ms') IS NOT NULL
                ORDER BY created_at DESC LIMIT ?
            """, (window,))
            values = sorted([r[0] for r in c.fetchall() if r[0] is not None])
            if not values:
                return None
            return values[min(int(len(values) * 0.99), len(values) - 1)]
        finally:
            self.store._close(conn)

    def _metric_gini(self, window: int) -> float | None:
        conn = self.store._connect()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT tool_name, COUNT(*) FROM tool_usage_log
                WHERE created_at > datetime('now', '-7 days')
                GROUP BY tool_name
            """)
            counts = sorted([r[1] for r in c.fetchall()])
            if not counts or len(counts) < 2:
                return None
            n = len(counts)
            total = sum(counts)
            cumsum = sum((i + 1) * c for i, c in enumerate(counts))
            return (2 * cumsum) / (n * total) - (n + 1) / n
        finally:
            self.store._close(conn)

    def _in_cooldown(self, trigger: OptimizationTrigger) -> bool:
        last = self._last_fired.get(trigger.name)
        if last is None:
            return False
        return (time.time() - last) / 3600 < trigger.cooldown_hours

    def _record_event(self, trigger: OptimizationTrigger, value: float, result: Any):
        try:
            conn = self.store._connect()
            c = conn.cursor()
            c.execute("""
                INSERT INTO optimization_events
                (metric, value, threshold, action_taken, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (trigger.metric, value, trigger.threshold,
                  str(result)[:1000] if result else None, time.time()))
            self.store._close(conn)
        except Exception as e:
            logger.debug(f"Failed to record optimization event: {e}")

    def get_status(self) -> dict:
        """Get current optimization loop status."""
        status = {"call_count": self._call_count, "check_interval": self.CHECK_INTERVAL, "triggers": []}
        for t in self.triggers:
            value = self._compute_metric(t.metric, t.window_calls)
            status["triggers"].append({
                "name": t.name, "metric": t.metric,
                "current_value": value, "threshold": t.threshold,
                "direction": t.direction,
                "breached": (
                    (t.direction == "below" and value is not None and value < t.threshold) or
                    (t.direction == "above" and value is not None and value > t.threshold)
                ) if value is not None else None,
                "in_cooldown": self._in_cooldown(t),
                "last_fired": self._last_fired.get(t.name),
                "description": t.description,
            })
        return status
