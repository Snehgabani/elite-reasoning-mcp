"""Anti-pattern injection middleware.
Auto-injects relevant past mistakes into the orchestration response.
Closes the most important feedback loop: record_mistake → future context.
"""
import hashlib
import logging

from core.middleware.base import CallContext, CallResult, Middleware

logger = logging.getLogger(__name__)

# Token budget constraints
INJECTION_BUDGET = {
    'max_items': 3,
    'max_chars_per_item': 240,
    'max_total_chars': 720,
    'min_prompt_length': 50,
}


class AntiPatternInjectionMiddleware(Middleware):
    """Injects relevant past mistakes into orchestration responses."""
    name = "anti_pattern_injection"
    applies_to = {"orchestrate_request_tool"}

    def __init__(self, store, session_id: str = 'default'):
        self.store = store
        self.session_id = session_id

    async def after(self, ctx: CallContext, result: CallResult) -> CallResult:
        prompt = ctx.args.get('user_prompt', '')
        if len(prompt) < INJECTION_BUDGET['min_prompt_length']:
            return result

        try:
            # Search for relevant past mistakes
            hits = self.store.check_anti_patterns(
                prompt[:500], limit=INJECTION_BUDGET['max_items'] * 2
            )

            if not hits:
                return result

            # Dedupe by root_cause hash
            seen = set()
            unique = []
            for h in hits:
                rc_hash = hashlib.md5(h.get('root_cause', '').encode()).hexdigest()[:8]
                if rc_hash not in seen:
                    seen.add(rc_hash)
                    unique.append(h)

            # Take top N within budget
            unique = unique[:INJECTION_BUDGET['max_items']]

            # Format with budget
            bullets = []
            total_chars = 0
            for h in unique:
                mistake = h.get('mistake', '')[:120]
                fix = h.get('fix', '')[:100]
                line = f"- **{mistake}** → Fix: {fix}"
                if total_chars + len(line) > INJECTION_BUDGET['max_total_chars']:
                    break
                bullets.append(line)
                total_chars += len(line)

            if bullets:
                injection = "## ⚠️ Similar Past Mistakes\n" + "\n".join(bullets)
                result.augmentations.insert(0, injection)

                # Log injection event for measurement
                prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
                ap_ids = [h.get('id', 0) for h in unique[:len(bullets)]]
                try:
                    self.store.log_injection(self.session_id, ap_ids, prompt_hash)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Anti-pattern injection failed: {e}")

        return result
