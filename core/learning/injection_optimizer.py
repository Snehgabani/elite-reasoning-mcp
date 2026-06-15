"""Injection Optimizer — closes the injection feedback loop.

Reads injection_events (previously write-only), computes per-pattern
effectiveness, retires ineffective patterns, boosts effective ones."""
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class InjectionStats:
    """Per-anti-pattern injection statistics."""
    anti_pattern_id: int
    times_injected: int
    times_prevented: int
    times_recurred: int
    last_injected: float

    @property
    def effectiveness(self) -> float:
        total = self.times_prevented + self.times_recurred
        if total < 5:
            return 0.5  # neutral prior
        return self.times_prevented / total

    @property
    def staleness_days(self) -> float:
        return (time.time() - self.last_injected) / 86400 if self.last_injected else float('inf')


class InjectionOptimizer:
    """Optimizes the anti-pattern injection pool based on measured effectiveness.

    Lifecycle:
    1. AntiPatternInjectionMiddleware injects patterns into prompts
    2. injection_events table records what was injected and when
    3. This optimizer reads outcomes and adjusts eligibility
    4. Ineffective patterns are retired; effective ones get priority
    """

    EFFECTIVENESS_FLOOR = 0.30
    STALENESS_MAX_DAYS = 90
    MIN_INJECTIONS_TO_JUDGE = 20
    BOOST_THRESHOLD = 0.70

    def __init__(self, store):
        self.store = store

    def compute_injection_stats(self) -> list[InjectionStats]:
        """Aggregate injection outcomes per anti-pattern."""
        conn = self.store._connect()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT
                    json_each.value AS anti_pattern_id,
                    COUNT(*) AS times_injected,
                    SUM(CASE WHEN ie.outcome = 'prevented' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN ie.outcome = 'recurred' THEN 1 ELSE 0 END),
                    MAX(ie.injected_at)
                FROM injection_events ie,
                     json_each(ie.anti_pattern_ids)
                WHERE ie.outcome != 'unknown'
                GROUP BY json_each.value
            """)
            return [
                InjectionStats(
                    anti_pattern_id=int(r[0]),
                    times_injected=r[1],
                    times_prevented=r[2],
                    times_recurred=r[3],
                    last_injected=r[4] or 0,
                )
                for r in c.fetchall()
            ]
        except Exception as e:
            logger.error(f"Failed to compute injection stats: {e}")
            return []
        finally:
            self.store._close(conn)

    def adjust_injection_pool(self) -> dict:
        """Run optimization pass. Returns summary of changes."""
        stats = self.compute_injection_stats()
        retired = 0
        boosted = 0
        unchanged = 0

        for stat in stats:
            eligible = True
            reason = None
            effectiveness = None

            if (stat.effectiveness < self.EFFECTIVENESS_FLOOR
                    and stat.times_injected >= self.MIN_INJECTIONS_TO_JUDGE):
                eligible = False
                reason = f"ineffective ({stat.effectiveness:.0%} after {stat.times_injected} injections)"
                retired += 1
            elif (stat.staleness_days > self.STALENESS_MAX_DAYS
                    and stat.times_injected == 0):
                eligible = False
                reason = f"stale_never_used ({stat.staleness_days:.0f}d)"
                retired += 1
            elif stat.effectiveness > self.BOOST_THRESHOLD:
                effectiveness = stat.effectiveness
                boosted += 1
            else:
                unchanged += 1
                continue

            self._update_eligibility(stat.anti_pattern_id, eligible, reason, effectiveness)

        summary = {
            "total_evaluated": len(stats),
            "retired": retired,
            "boosted": boosted,
            "unchanged": unchanged,
            "timestamp": time.time(),
        }
        logger.info(f"Injection pool adjusted: {summary}")
        return summary

    def rank_for_injection(self, candidate_ids: list[int], query_embedding=None) -> list[int]:
        """Re-rank injection candidates by effectiveness."""
        if not candidate_ids:
            return []
        conn = self.store._connect()
        try:
            c = conn.cursor()
            placeholders = ",".join("?" * len(candidate_ids))
            c.execute(
                f"SELECT id, COALESCE(injection_effectiveness, 0.5) as eff "
                f"FROM anti_patterns WHERE id IN ({placeholders}) "
                f"AND COALESCE(injection_eligible, 1) = 1",
                candidate_ids
            )
            rows = {r[0]: r[1] for r in c.fetchall()}
        finally:
            self.store._close(conn)

        scored = [(cid, 0.5 + rows.get(cid, 0.5)) for cid in candidate_ids]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored]

    def _update_eligibility(self, anti_pattern_id: int, eligible: bool,
                            reason: str | None, effectiveness: float | None):
        """Update anti-pattern's injection eligibility."""
        conn = self.store._connect()
        try:
            c = conn.cursor()
            c.execute(
                "UPDATE anti_patterns SET injection_eligible = ?, "
                "injection_disabled_reason = ?, injection_effectiveness = ? "
                "WHERE id = ?",
                (1 if eligible else 0, reason, effectiveness, anti_pattern_id)
            )
        except Exception as e:
            logger.error(f"Failed to update eligibility for AP {anti_pattern_id}: {e}")
        finally:
            self.store._close(conn)
