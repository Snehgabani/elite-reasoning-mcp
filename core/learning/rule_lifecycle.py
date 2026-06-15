"""Rule Lifecycle Daemon — manages prevention rule state machine.

States: probation → active → trusted → dormant → retired

Runs periodically (via OptimizationLoop) to evaluate all rules and
transition them based on measured effectiveness."""
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RuleState:
    """Snapshot of a prevention rule's current state."""
    id: int
    rule_name: str
    lifecycle_state: str
    times_triggered: int
    evaluation_count: int
    false_positive_count: int
    true_positive_count: int
    last_triggered_at: float | None
    promoted_at: float | None
    created_at: float


class RuleLifecycle:
    """Evaluates and transitions prevention rules through lifecycle states.

    State machine:
        probation → active      (fire rate >= 5%, 50+ evals)
        probation → retired     (1000+ evals, 0 fires)
        active → trusted        (200+ evals, <10% FP rate)
        active → dormant        (no fires for 30 days)
        active → probation      (>70% FP rate — demote)
        dormant → active        (fires again)
        dormant → retired       (60+ days dormant)
        trusted → active        (FP rate climbs above 20%)
    """

    PROBATION_MIN_EVALS = 50
    PROBATION_PROMOTION_FIRE_RATE = 0.05
    RETIREMENT_EVALS = 1000
    TRUSTED_MIN_EVALS = 200
    TRUSTED_MAX_FP_RATE = 0.10
    TRUSTED_DEMOTION_FP_RATE = 0.20
    DORMANT_THRESHOLD_DAYS = 30
    DORMANT_RETIREMENT_DAYS = 60
    FP_RATE_FOR_DEMOTION = 0.70

    def __init__(self, store):
        self.store = store

    def tick(self) -> dict:
        """Evaluate all rules and transition states. Returns summary."""
        rules = self._load_all_rules()
        transitions = []

        for rule in rules:
            new_state = self._next_state(rule)
            if new_state and new_state != rule.lifecycle_state:
                reason = self._reason(rule, new_state)
                self._transition(rule.id, new_state, reason)
                transitions.append({
                    "rule_id": rule.id,
                    "rule_name": rule.rule_name,
                    "from": rule.lifecycle_state,
                    "to": new_state,
                    "reason": reason,
                })
                logger.info(
                    f"Rule '{rule.rule_name}' transitioned: "
                    f"{rule.lifecycle_state} → {new_state} ({reason})"
                )

        return {
            "total_rules": len(rules),
            "transitions": len(transitions),
            "details": transitions,
            "timestamp": time.time(),
        }

    def record_rule_outcome(self, rule_id: int, was_useful: bool):
        """Record whether a rule firing was a true or false positive."""
        conn = self.store._connect()
        try:
            c = conn.cursor()
            col = "true_positive_count" if was_useful else "false_positive_count"
            c.execute(
                f"UPDATE prevention_rules SET {col} = COALESCE({col}, 0) + 1 WHERE id = ?",
                (rule_id,)
            )
        finally:
            self.store._close(conn)

    def _next_state(self, rule: RuleState) -> str | None:
        """Pure function: compute next state from current state + metrics."""
        state = rule.lifecycle_state or 'probation'

        if state == 'probation':
            if rule.evaluation_count >= self.PROBATION_MIN_EVALS:
                fire_rate = rule.times_triggered / max(1, rule.evaluation_count)
                if fire_rate >= self.PROBATION_PROMOTION_FIRE_RATE:
                    return 'active'
                elif rule.evaluation_count >= self.RETIREMENT_EVALS:
                    return 'retired'
            return None

        elif state == 'active':
            if rule.last_triggered_at:
                days_since = (time.time() - rule.last_triggered_at) / 86400
                if days_since > self.DORMANT_THRESHOLD_DAYS:
                    return 'dormant'
            elif rule.evaluation_count > self.PROBATION_MIN_EVALS:
                return 'dormant'

            total_fires = rule.true_positive_count + rule.false_positive_count
            if total_fires > 0:
                fp_rate = rule.false_positive_count / total_fires
                if fp_rate > self.FP_RATE_FOR_DEMOTION:
                    return 'probation'

            if rule.evaluation_count >= self.TRUSTED_MIN_EVALS and total_fires > 0:
                fp_rate = rule.false_positive_count / total_fires
                if fp_rate < self.TRUSTED_MAX_FP_RATE:
                    return 'trusted'
            return None

        elif state == 'trusted':
            total_fires = rule.true_positive_count + rule.false_positive_count
            if total_fires > 10:
                fp_rate = rule.false_positive_count / total_fires
                if fp_rate > self.TRUSTED_DEMOTION_FP_RATE:
                    return 'active'
            return None

        elif state == 'dormant':
            if rule.last_triggered_at:
                days_since = (time.time() - rule.last_triggered_at) / 86400
                if days_since < self.DORMANT_THRESHOLD_DAYS:
                    return 'active'
                elif days_since > self.DORMANT_RETIREMENT_DAYS:
                    return 'retired'
            return None

        return None

    def _reason(self, rule: RuleState, new_state: str) -> str:
        """Generate human-readable transition reason."""
        total = rule.true_positive_count + rule.false_positive_count
        fp_rate = (rule.false_positive_count / total * 100) if total > 0 else 0
        fire_rate = (rule.times_triggered / max(1, rule.evaluation_count) * 100)

        reasons = {
            'active': f"Fire rate {fire_rate:.1f}% after {rule.evaluation_count} evals",
            'trusted': f"Low FP rate ({fp_rate:.0f}%) over {rule.evaluation_count} evals",
            'dormant': f"No fires in {self.DORMANT_THRESHOLD_DAYS}+ days",
            'retired': f"Insufficient value after {rule.evaluation_count} evals",
            'probation': f"High FP rate ({fp_rate:.0f}%) — demoted",
        }
        return reasons.get(new_state, f"Transitioned to {new_state}")

    def _transition(self, rule_id: int, new_state: str, reason: str):
        """Apply state transition to the database."""
        conn = self.store._connect()
        try:
            c = conn.cursor()
            updates = {"lifecycle_state": new_state}
            if new_state in ('active', 'trusted'):
                updates["promoted_at"] = time.time()
            elif new_state == 'retired':
                updates["retired_at"] = time.time()
                updates["enabled"] = 0

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [rule_id]
            c.execute(f"UPDATE prevention_rules SET {set_clause} WHERE id = ?", values)
        except Exception as e:
            logger.error(f"Failed to transition rule {rule_id}: {e}")
        finally:
            self.store._close(conn)

    def _load_all_rules(self) -> list[RuleState]:
        """Load all non-retired rules for evaluation."""
        conn = self.store._connect()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT id, rule_name,
                       COALESCE(lifecycle_state, 'probation'),
                       COALESCE(times_triggered, 0),
                       COALESCE(evaluation_count, 0),
                       COALESCE(false_positive_count, 0),
                       COALESCE(true_positive_count, 0),
                       last_triggered_at, promoted_at, created_at
                FROM prevention_rules
                WHERE COALESCE(lifecycle_state, 'probation') != 'retired'
            """)
            return [
                RuleState(
                    id=r[0], rule_name=r[1], lifecycle_state=r[2],
                    times_triggered=r[3], evaluation_count=r[4],
                    false_positive_count=r[5], true_positive_count=r[6],
                    last_triggered_at=r[7], promoted_at=r[8],
                    created_at=r[9] if isinstance(r[9], (int, float)) else 0,
                )
                for r in c.fetchall()
            ]
        except Exception as e:
            logger.error(f"Failed to load rules: {e}")
            return []
        finally:
            self.store._close(conn)
