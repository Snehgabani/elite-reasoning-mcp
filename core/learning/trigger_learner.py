"""Trigger Learner — data-driven trigger assignment for prevention rules.

Analyzes trigger_effectiveness table to learn which triggers work best
for which detection types. Uses Wilson score lower bound for small-sample confidence."""
import logging
import math

logger = logging.getLogger(__name__)

DEFAULT_TRIGGER_MAP = {
    "security": "phase.before:code_change",
    "performance": "phase.before:commit",
    "quality": "prompt.received",
    "reliability": "tool.after:*",
    "architecture": "phase.before:design",
}


def wilson_lower_bound(successes: int, total: int, z: float = 1.96) -> float:
    """Wilson score lower bound — prevents 1/1 from beating 50/60."""
    if total == 0:
        return 0.0
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (centre - spread) / denominator


class TriggerLearner:
    """Learns optimal trigger assignments from measured outcomes.

    After ~10+ samples per (detection_type, trigger_event) pair,
    data-driven selection replaces the hardcoded DEFAULT_TRIGGER_MAP.
    """

    MIN_SAMPLES = 10

    def __init__(self, store):
        self.store = store

    def learn(self) -> dict:
        """Run learning pass. Returns best triggers per detection type."""
        conn = self.store._connect()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT detection_type, trigger_event,
                       COALESCE(fired_count, 0),
                       COALESCE(quality_improved_count, 0),
                       COALESCE(quality_degraded_count, 0)
                FROM trigger_effectiveness
                WHERE COALESCE(fired_count, 0) >= ?
            """, (self.MIN_SAMPLES,))
            rows = c.fetchall()
        except Exception as e:
            logger.error(f"Failed to load trigger effectiveness: {e}")
            return {"error": str(e)}
        finally:
            self.store._close(conn)

        by_type: dict[str, list] = {}
        for r in rows:
            by_type.setdefault(r[0], []).append({
                "trigger": r[1],
                "fired": r[2],
                "improved": r[3],
                "degraded": r[4],
                "wilson": wilson_lower_bound(r[3], r[2]),
            })

        best_triggers = {}
        for det_type, candidates in by_type.items():
            best = max(candidates, key=lambda c: c["wilson"])
            best_triggers[det_type] = {
                "trigger": best["trigger"],
                "wilson_score": round(best["wilson"], 3),
                "samples": best["fired"],
                "source": "learned",
            }

        for det_type, default_trigger in DEFAULT_TRIGGER_MAP.items():
            if det_type not in best_triggers:
                best_triggers[det_type] = {
                    "trigger": default_trigger,
                    "wilson_score": None,
                    "samples": 0,
                    "source": "default",
                }

        return {
            "best_triggers": best_triggers,
            "total_data_points": len(rows),
            "learned_count": sum(1 for v in best_triggers.values() if v["source"] == "learned"),
            "default_count": sum(1 for v in best_triggers.values() if v["source"] == "default"),
        }

    def suggest_trigger(self, detection_type: str) -> str:
        """Get the best trigger for a detection type."""
        conn = self.store._connect()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT trigger_event, fired_count, quality_improved_count
                FROM trigger_effectiveness
                WHERE detection_type = ? AND COALESCE(fired_count, 0) >= ?
            """, (detection_type, self.MIN_SAMPLES))
            candidates = c.fetchall()
            if not candidates:
                return DEFAULT_TRIGGER_MAP.get(detection_type, "prompt.received")
            best = max(candidates, key=lambda c: wilson_lower_bound(c[2], c[1]))
            return best[0]
        except Exception:
            return DEFAULT_TRIGGER_MAP.get(detection_type, "prompt.received")
        finally:
            self.store._close(conn)
