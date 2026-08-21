"""Prevention rule middleware with EventBus and semantic matching.
Fixes the 0/26 rule firing rate by:
1. Using canonical event vocabulary (tool.before:*, prompt.received, etc.)
2. Tracking evaluation_count vs times_triggered for observability
3. Supporting wildcard event matching
"""

import logging
import time
from collections import defaultdict
from typing import Optional

from core.middleware.base import CallContext, CallResult, Middleware

logger = logging.getLogger(__name__)

# ── Canonical Event Vocabulary ──
# tool.before:<tool_name>    tool.after:<tool_name>    tool.before:*    tool.after:*
# prompt.received            prompt.complexity_high
# phase.before:<phase>       phase.after:<phase>       (design, code_change, commit, audit, deploy)
# memory.write:<table>       memory.write:*
# session.start              session.end

# Migration map from old trigger vocabulary
TRIGGER_MIGRATION = {
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

# Intent-to-phase mapping for the orchestrator
INTENT_PHASE_MAP = {
    "design": "design",
    "architecture": "design",
    "build": "code_change",
    "create": "code_change",
    "fix": "code_change",
    "refactor": "code_change",
    "debug": "code_change",
    "deploy": "deploy",
    "audit": "audit",
    "test": "code_change",
    "security": "code_change",
    "research": "audit",
}

PROMPT_TOOLS = frozenset({"elite_prepare", "orchestrate_request_tool", "workflow_run"})


def _phase_for_prompt(prompt: str) -> str | None:
    """Map gateway prompts to the same canonical phase events as legacy tools."""
    text = (prompt or "").lower()
    if any(term in text for term in ("architecture", "architect", "design", "schema", "data model")):
        return "design"
    if any(term in text for term in ("deploy", "publish", "ship to production")):
        return "deploy"
    if any(term in text for term in ("audit", "review", "inspect", "verify")):
        return "audit"
    if any(term in text for term in ("build", "create", "implement", "fix", "debug", "refactor", "test")):
        return "code_change"
    return None


class EventBus:
    """Event bus for prevention rules with wildcard matching and observability."""

    def __init__(self, store):
        self.store = store
        self._rules_by_event: dict[str, list[dict]] = {}
        self._reload()

    def _reload(self):
        """Load and index all enabled prevention rules."""
        try:
            rules = self.store.get_active_prevention_rules()
            self._rules_by_event = defaultdict(list)
            for r in rules:
                trigger = str(r.get("trigger_event") or "")
                # Migrate old vocabulary
                trigger = TRIGGER_MIGRATION.get(trigger, trigger)
                self._rules_by_event[trigger].append(r)
        except Exception as e:
            logger.warning(f"EventBus reload failed: {e}")
            self._rules_by_event = {}

    def emit(self, event: str, payload: dict) -> list[str]:
        """Emit an event and collect all matching rule warnings."""
        warnings = []
        matched_rules = []

        # Exact match
        matched_rules.extend(self._rules_by_event.get(event, []))

        # Wildcard match: tool.after:record_decision → also check tool.after:*
        if ":" in event:
            wildcard = event.split(":")[0] + ":*"
            matched_rules.extend(self._rules_by_event.get(wildcard, []))

        for rule in matched_rules:
            start = time.perf_counter()
            error = None
            try:
                # Keyword-based check against payload
                check = rule.get("check_query", rule.get("check", "")).lower()
                context_text = " ".join(str(v) for v in payload.values() if isinstance(v, str)).lower()
                # Phase rules are intentionally event-gated: their check text
                # describes the review to run, not a keyword condition that
                # happens to be present in a user prompt. Other rules retain
                # keyword matching to avoid broad, noisy reminders.
                if event.startswith("phase."):
                    matched = True
                else:
                    check_words = [word for word in check.split() if len(word) > 3]
                    match_count = sum(1 for word in check_words if word in context_text)
                    matched = bool(check_words) and match_count / len(check_words) >= 0.25
                if matched:
                    self.store.increment_rule_trigger(rule["id"])
                    warnings.append(
                        f"Rule `{rule.get('name', rule.get('rule_name', 'unknown'))}` "
                        f"[{rule.get('severity', 'P1')}] fired: "
                        f"{rule.get('action_on_match', rule.get('action', ''))}"
                    )
            except Exception as e:
                error = str(e)
                logger.warning(f"Rule evaluation error: {e}")
            finally:
                # Observability: always record evaluation
                elapsed_ms = (time.perf_counter() - start) * 1000
                try:
                    self.store.update_rule_evaluation(rule["id"], error=error, check_ms=elapsed_ms)
                except Exception as e:
                    logger.debug(f"Rule evaluation tracking failed for rule {rule.get('id', '?')}: {e}")

        return warnings


class PreventionRuleMiddleware(Middleware):
    """Fires prevention rules via EventBus on every tool call."""

    name = "prevention_rules"
    applies_to = "*"  # Evaluate on every tool

    EXEMPT_TOOLS = frozenset(
        {
            "get_user_profile",
            "update_user_config",
        }
    )

    def __init__(self, store, reload_interval: int = 50):
        self.bus = EventBus(store)
        self._eval_count = 0
        self._reload_interval = reload_interval

    async def before(self, ctx: CallContext) -> Optional[CallResult]:
        # Periodic reload to pick up rules added at runtime
        self._eval_count += 1
        if self._eval_count % self._reload_interval == 0:
            self.bus._reload()

        if ctx.tool_name in self.EXEMPT_TOOLS:
            return None

        payload = {
            "tool_name": ctx.tool_name,
            "args_text": " ".join(str(v) for v in ctx.args.values() if isinstance(v, str))[:500],
        }

        # Emit tool.before:<tool_name>
        warnings = self.bus.emit(f"tool.before:{ctx.tool_name}", payload)

        # NOTE: EventBus.emit() already handles wildcard matching internally
        # (tool.before:<name> → also checks tool.before:*), so no explicit
        # wildcard emit is needed here.

        # Gateway and legacy prompt-bearing tools all emit the same canonical
        # events so prevention coverage does not depend on the profile.
        if ctx.tool_name in PROMPT_TOOLS:
            prompt = ctx.args.get("user_prompt", "")
            payload["prompt"] = prompt[:500]
            warnings.extend(self.bus.emit("prompt.received", payload))
            phase = _phase_for_prompt(prompt)
            if phase:
                payload["phase"] = phase
                ctx.metadata["workflow_phase"] = phase
                warnings.extend(self.bus.emit(f"phase.before:{phase}", payload))

        if warnings:
            ctx.metadata["prevention_warnings"] = warnings

        return None  # Never short-circuit — just record

    async def after(self, ctx: CallContext, result: CallResult) -> CallResult:
        # Emit tool.after:<tool_name>
        payload = {"tool_name": ctx.tool_name}
        post_warnings = self.bus.emit(f"tool.after:{ctx.tool_name}", payload)

        # Inject any prevention warnings into result
        all_warnings = ctx.metadata.get("prevention_warnings", []) + post_warnings
        if all_warnings:
            result.augmentations.insert(0, "Prevention: " + " | ".join(all_warnings))
        return result
