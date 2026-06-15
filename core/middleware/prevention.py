"""Prevention rule middleware with EventBus and semantic matching.
Fixes the 0/26 rule firing rate by:
1. Using canonical event vocabulary (tool.before:*, prompt.received, etc.)
2. Tracking evaluation_count vs times_triggered for observability
3. Supporting wildcard event matching
"""
import time
import logging
from collections import defaultdict
from typing import Optional
from core.middleware.base import Middleware, CallContext, CallResult

logger = logging.getLogger(__name__)

# ── Canonical Event Vocabulary ──
# tool.before:<tool_name>    tool.after:<tool_name>    tool.before:*    tool.after:*
# prompt.received            prompt.complexity_high
# phase.before:<phase>       phase.after:<phase>       (design, code_change, commit, audit, deploy)
# memory.write:<table>       memory.write:*
# session.start              session.end

# Migration map from old trigger vocabulary
TRIGGER_MIGRATION = {
    'on_prompt': 'prompt.received',
    'prompt_received': 'prompt.received',
    'on_startup': 'session.start',
    'after_tool_call': 'tool.after:*',
    'before_design': 'phase.before:design',
    'before_code_change': 'phase.before:code_change',
    'after_code_change': 'phase.after:code_change',
    'pre_commit': 'phase.before:commit',
    'after_audit': 'phase.after:audit',
}

# Intent-to-phase mapping for the orchestrator
INTENT_PHASE_MAP = {
    'design': 'design',
    'architecture': 'design',
    'build': 'code_change',
    'create': 'code_change',
    'fix': 'code_change',
    'refactor': 'code_change',
    'debug': 'code_change',
    'deploy': 'deploy',
    'audit': 'audit',
    'test': 'code_change',
}


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
                trigger = r.get('trigger_event', '')
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
        if ':' in event:
            wildcard = event.split(':')[0] + ':*'
            matched_rules.extend(self._rules_by_event.get(wildcard, []))
        
        for rule in matched_rules:
            start = time.perf_counter()
            error = None
            try:
                # Keyword-based check against payload
                check = rule.get('check_query', rule.get('check', '')).lower()
                context_text = ' '.join(str(v) for v in payload.values() if isinstance(v, str)).lower()
                
                check_words = [w for w in check.split() if len(w) > 3]
                if check_words:
                    match_count = sum(1 for w in check_words if w in context_text)
                    match_ratio = match_count / len(check_words)
                    
                    if match_ratio >= 0.25:  # 25% keyword overlap
                        self.store.increment_rule_trigger(rule['id'])
                        warnings.append(
                            f"🛡️ Rule `{rule.get('name', rule.get('rule_name', 'unknown'))}` "
                            f"[{rule.get('severity', 'P1')}] fired:\n"
                            f"   Check: {check}\n"
                            f"   Action: {rule.get('action_on_match', rule.get('action', ''))}"
                        )
            except Exception as e:
                error = str(e)
                logger.warning(f"Rule evaluation error: {e}")
            finally:
                # Observability: always record evaluation
                elapsed_ms = (time.perf_counter() - start) * 1000
                try:
                    self.store.update_rule_evaluation(rule['id'], error=error, check_ms=elapsed_ms)
                except Exception:
                    pass
        
        return warnings


class PreventionRuleMiddleware(Middleware):
    """Fires prevention rules via EventBus on every tool call."""
    name = "prevention_rules"
    applies_to = "*"  # Evaluate on every tool
    
    EXEMPT_TOOLS = frozenset({
        'get_user_profile', 'update_user_config',
    })
    
    def __init__(self, store):
        self.bus = EventBus(store)
    
    async def before(self, ctx: CallContext) -> Optional[CallResult]:
        if ctx.tool_name in self.EXEMPT_TOOLS:
            return None
        
        payload = {
            'tool_name': ctx.tool_name,
            'args_text': ' '.join(str(v) for v in ctx.args.values() if isinstance(v, str))[:500],
        }
        
        # Emit tool.before:<tool_name>
        warnings = self.bus.emit(f'tool.before:{ctx.tool_name}', payload)
        
        # Emit tool.before:*
        warnings.extend(self.bus.emit('tool.before:*', payload))
        
        # For orchestrate — also emit prompt.received
        if ctx.tool_name == 'orchestrate_request_tool':
            prompt = ctx.args.get('user_prompt', '')
            payload['prompt'] = prompt[:500]
            warnings.extend(self.bus.emit('prompt.received', payload))
        
        if warnings:
            ctx.metadata['prevention_warnings'] = warnings
        
        return None  # Never short-circuit — just record
    
    async def after(self, ctx: CallContext, result: CallResult) -> CallResult:
        # Emit tool.after:<tool_name>
        payload = {'tool_name': ctx.tool_name}
        post_warnings = self.bus.emit(f'tool.after:{ctx.tool_name}', payload)
        
        # Inject any prevention warnings into result
        all_warnings = ctx.metadata.get('prevention_warnings', []) + post_warnings
        if all_warnings:
            result.augmentations.insert(0,
                "╔══ 🛡️ PREVENTION RULES FIRED ══╗\n"
                + "\n".join(all_warnings)
                + "\n╚═══════════════════════════════╝"
            )
        return result
