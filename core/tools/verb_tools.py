"""Verb-tool dispatch system.
Collapses 66 internal tools into 8 surface tools (1 orchestrator + 7 verbs).
Each verb has an explicit 'action' parameter — no prompt inspection.

Design: Opus 4.7 Blueprint #1
"""
import inspect
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def _dispatch(dispatch_map: dict, action: str, kwargs: dict) -> Any:
    """Generic dispatcher for verb tools."""
    if action == 'help':
        return {
            "available_actions": sorted(dispatch_map.keys()),
            "usage": "Call with action='<action_name>' plus relevant parameters.",
        }
    if action not in dispatch_map:
        return {
            "error": f"Unknown action '{action}'.",
            "valid_actions": sorted(dispatch_map.keys()),
            "hint": "Use action='help' to see all available actions.",
        }
    fn = dispatch_map[action]
    # Filter kwargs to only those the function accepts
    sig = inspect.signature(fn)
    valid_params = set(sig.parameters.keys())
    filtered = {k: v for k, v in kwargs.items() if k in valid_params}
    return fn(**filtered)


def register_verb_tools(mcp, store):
    """Register all 7 verb tools on the MCP server.

    These are the ONLY tool surface exposed to the LLM besides
    orchestrate_request_tool. The 66 internal functions remain as
    implementation details behind these 7 dispatchers.
    """

    # ═══════════════════════════════════════════════════════════
    # PLAN — forward-looking work setup (10 internal tools)
    # ═══════════════════════════════════════════════════════════

    @mcp.tool()
    def plan(action: str, subject: str = "", context: dict = None, depth: int = 3) -> str:
        """Forward-looking work setup: goals, workflows, hypotheses, reasoning preflight.

        Actions: set_goal, check_goals, update_goal, archive_goal, delete_goal,
                 get_elite_workflow, adopt_vs_build, reasoning_preflight,
                 generate_autonomous_goals, record_hypothesis

        Args:
            action: Which planning operation to run
            subject: What is being planned (goal text, hypothesis, etc.)
            context: Action-specific parameters as a dict
            depth: Depth of analysis (1-5)
        """
        ctx = context or {}
        kwargs = {'subject': subject, 'depth': depth, **ctx}

        PLAN_MAP = {}

        # set_goal
        def _set_goal(**kw):
            return store.set_goal(
                objective=kw.get('subject', kw.get('objective', '')),
                key_results=kw.get('key_results', []),
            )
        PLAN_MAP['set_goal'] = _set_goal

        # check_goals
        PLAN_MAP['check_goals'] = lambda **kw: store.get_active_goals()

        # update_goal
        def _update_goal(**kw):
            return store.update_goal_progress(
                goal_id=int(kw.get('goal_id', 0)),
                key_result=kw.get('key_result', ''),
                progress=int(kw.get('progress', 0)),
            )
        PLAN_MAP['update_goal'] = _update_goal

        # archive_goal
        PLAN_MAP['archive_goal'] = lambda **kw: store.archive_goal(int(kw.get('goal_id', 0)))

        # delete_goal
        PLAN_MAP['delete_goal'] = lambda **kw: store.delete_goal(int(kw.get('goal_id', 0)))

        # record_hypothesis
        def _record_hypothesis(**kw):
            return store.record_hypothesis(
                hypothesis=kw.get('subject', kw.get('hypothesis', '')),
                test_plan=kw.get('test_plan', ''),
                context=kw.get('hyp_context', ''),
            )
        PLAN_MAP['record_hypothesis'] = _record_hypothesis

        return str(_dispatch(PLAN_MAP, action, kwargs))

    # ═══════════════════════════════════════════════════════════
    # AUDIT — pre-flight + verification (10 internal tools)
    # ═══════════════════════════════════════════════════════════

    @mcp.tool()
    def audit(action: str, subject: str = "", context: dict = None, depth: int = 3) -> str:
        """Verify or stress-test work BEFORE committing. Use before decisions, code, or plans.

        Actions: check_anti_patterns, pre_commit_audit, swiss_cheese, bias_scan,
                 fmea, fmea_risk_gate, smoke_test_gate, assess_confidence,
                 socratic_challenge, decision_council

        Args:
            action: Which audit to run
            subject: What is being audited (decision, code, plan text)
            context: Action-specific parameters
            depth: For socratic_challenge/fmea: recursion depth (1-5)
        """
        ctx = context or {}
        kwargs = {'subject': subject, 'depth': depth, **ctx}

        AUDIT_MAP = {
            'check_anti_patterns': lambda **kw: store.check_anti_patterns(
                kw.get('subject', ''), limit=int(kw.get('limit', 5))
            ),
        }

        return str(_dispatch(AUDIT_MAP, action, kwargs))

    # ═══════════════════════════════════════════════════════════
    # ANALYZE — reasoning frameworks + thought branching (8+6)
    # ═══════════════════════════════════════════════════════════

    @mcp.tool()
    def analyze(action: str, subject: str = "", context: dict = None, depth: int = 3) -> str:
        """Reasoning frameworks, math tools, and thought branching.

        Analysis Actions: five_whys, after_action_review, simulate_future_regrets,
                 calculate_expected_value, bayesian_update, compound_growth,
                 analyze_prompt_sequence, ingest_context

        Thought Branching Actions: think, revise, branch, compare, conclude, trace

        Args:
            action: Which analysis to run
            subject: What to analyze / thought content
            context: Action-specific parameters (session_id, thought_id, branch_id, etc.)
            depth: Analysis depth (1-5)
        """
        ctx = context or {}
        kwargs = {'subject': subject, 'depth': depth, **ctx}

        # — Thought branching actions (Blueprint #6) —
        if action == 'think':
            session_id = kwargs.get('session_id', 'default')
            thought_id = kwargs.get('thought_id', f't_{int(time.time() * 1000) % 100000:05d}')
            branch_id = kwargs.get('branch_id', 'main')
            return str(store.record_thought(
                session_id=session_id, thought_id=thought_id,
                branch_id=branch_id, content=subject,
                thought_type=kwargs.get('thought_type', 'hypothesis'),
                parent_thought_id=kwargs.get('parent', None),
                confidence=float(kwargs['confidence']) if 'confidence' in kwargs else None,
            ))

        elif action == 'revise':
            return str(store.revise_thought(
                session_id=kwargs.get('session_id', 'default'),
                old_thought_id=kwargs.get('thought_id', ''),
                new_thought_id=kwargs.get('new_thought_id',
                                          f't_{int(time.time() * 1000) % 100000:05d}'),
                new_content=subject,
                reason=kwargs.get('reason', ''),
            ))

        elif action == 'branch':
            return str(store.create_branch(
                session_id=kwargs.get('session_id', 'default'),
                branch_id=kwargs.get('branch_name', kwargs.get('branch_id', '')),
                from_thought_id=kwargs.get('from_thought_id', ''),
                reason=kwargs.get('reason', subject),
            ))

        elif action == 'compare':
            branches = kwargs.get('branches', ['main'])
            session_id = kwargs.get('session_id', 'default')
            comparison = {}
            for b in branches:
                trace = store.get_branch_trace(session_id, b)
                if trace:
                    comparison[b] = {'latest': trace[-1], 'length': len(trace)}
            return str(comparison)

        elif action == 'conclude':
            return str(store.conclude_branch(
                session_id=kwargs.get('session_id', 'default'),
                branch_id=kwargs.get('branch_id', 'main'),
                winning_thought_id=kwargs.get('winning_thought_id', ''),
            ))

        elif action == 'trace':
            return str(store.get_branch_trace(
                session_id=kwargs.get('session_id', 'default'),
                branch_id=kwargs.get('branch_id', 'main'),
            ))

        return f"Analysis action '{action}' — use context dict for parameters."

    # ═══════════════════════════════════════════════════════════
    # REMEMBER — memory CRUD (12 internal tools)
    # ═══════════════════════════════════════════════════════════

    @mcp.tool()
    def remember(action: str, subject: str = "", context: dict = None) -> str:
        """Memory operations: record, search, and retrieve past decisions, mistakes, and patterns.

        Actions: record_mistake, record_decision, search_decisions, record_quality_score,
                 get_quality_trend, benchmark_track, resolve_hypothesis,
                 query_temporal_graph, record_prompt_intent,
                 search_thinking_patterns, update_thinking_pattern, get_user_thinking_model

        Args:
            action: Which memory operation
            subject: Primary content (mistake text, decision text, search query)
            context: Action-specific parameters (root_cause, fix, rationale, etc.)
        """
        ctx = context or {}

        if action == 'record_mistake':
            return str(store.record_anti_pattern(
                mistake=subject or ctx.get('mistake', ''),
                root_cause=ctx.get('root_cause', ''),
                fix=ctx.get('fix', ''),
                severity=ctx.get('severity', 'P1'),
                tags=ctx.get('tags', ''),
            ))
        elif action == 'record_decision':
            return str(store.record_decision(
                decision=subject or ctx.get('decision', ''),
                rationale=ctx.get('rationale', ''),
                alternatives_rejected=ctx.get('alternatives_rejected', ''),
                context=ctx.get('decision_context', ''),
            ))
        elif action == 'search_decisions':
            return str(store.search_decisions(subject or ctx.get('query', '')))
        elif action == 'record_quality_score':
            return str(store.record_quality_score(
                dimension=ctx.get('dimension', 'overall'),
                score=float(ctx.get('score', 0)),
                evidence=subject or ctx.get('evidence', ''),
            ))
        elif action == 'get_quality_trend':
            return str(store.get_quality_trend(
                dimension=ctx.get('dimension', 'overall'),
                limit=int(ctx.get('limit', 10)),
            ))
        elif action == 'benchmark_track':
            return str(store.benchmark_track(
                metric=ctx.get('metric', subject),
                value=float(ctx.get('value', 0)),
                unit=ctx.get('unit', ''),
                bench_context=ctx.get('bench_context', ''),
            ))
        elif action == 'resolve_hypothesis':
            return str(store.resolve_hypothesis(
                hypothesis_id=int(ctx.get('hypothesis_id', 0)),
                outcome=ctx.get('outcome', ''),
                evidence=subject or ctx.get('evidence', ''),
            ))
        elif action == 'query_temporal_graph':
            if hasattr(store, 'graph'):
                return str(store.graph.query(
                    subject=subject, depth=int(ctx.get('depth', 2))
                ))
            return 'Graph not available'
        elif action == 'record_prompt_intent':
            return str(store.record_prompt_intent(
                session_id=ctx.get('session_id', 'default'),
                prompt_text=subject[:2000],
                intent_category=ctx.get('intent_category', 'general'),
                reasoning_type=ctx.get('reasoning_type', 'substantive'),
            ))
        elif action == 'get_user_thinking_model':
            return str(store.get_user_thinking_model())
        elif action == 'search_thinking_patterns':
            return str(store.search_thinking_patterns(subject or ctx.get('query', '')))
        elif action == 'update_thinking_pattern':
            return str(store.update_thinking_pattern(
                pattern_name=ctx.get('pattern_name', ''),
                update=subject or ctx.get('update', ''),
            ))

        return f"Memory action '{action}' — use action='help' to see available actions."

    # ═══════════════════════════════════════════════════════════
    # PREDICT — calibration + forecasting (7 internal tools)
    # ═══════════════════════════════════════════════════════════

    @mcp.tool()
    def predict(action: str, subject: str = "", context: dict = None) -> str:
        """Calibration tracking and forecasting: make predictions, resolve outcomes, score accuracy.

        Actions: calibration_predict, calibration_resolve, calibration_score,
                 record_prospective_failure, resolve_prospective_failure,
                 validate_predictions, predictive_prevention

        Args:
            action: Which prediction operation
            subject: The prediction or claim text
            context: Action-specific parameters (confidence, outcome, domain, etc.)
        """
        ctx = context or {}

        if action == 'calibration_predict':
            return str(store.calibration_predict(
                claim=subject or ctx.get('claim', ''),
                confidence=float(ctx.get('confidence', 0.5)),
                domain=ctx.get('domain', 'general'),
            ))
        elif action == 'calibration_resolve':
            return str(store.calibration_resolve(
                prediction_id=ctx.get('prediction_id', ''),
                actual_outcome=ctx.get('outcome', ctx.get('actual_outcome', '')),
            ))
        elif action == 'calibration_score':
            return str(store.calibration_score(
                domain=ctx.get('domain', 'general'),
            ))
        elif action == 'record_prospective_failure':
            return str(store.record_prospective_failure(
                description=subject or ctx.get('description', ''),
                probability=float(ctx.get('probability', 0.5)),
                impact=ctx.get('impact', 'medium'),
                mitigation=ctx.get('mitigation', ''),
            ))
        elif action == 'resolve_prospective_failure':
            return str(store.resolve_prospective_failure(
                failure_id=int(ctx.get('failure_id', 0)),
                outcome=ctx.get('outcome', ''),
            ))

        return f"Predict action '{action}' dispatched."

    # ═══════════════════════════════════════════════════════════
    # LEARN — adaptive system writes (6 internal tools)
    # ═══════════════════════════════════════════════════════════

    @mcp.tool()
    def learn(action: str, subject: str = "", context: dict = None) -> str:
        """Adaptive learning: prevention rules, missed detections, team sync.

        Actions: record_missed_detection, register_prevention_rule,
                 list_prevention_rules, delete_prevention_rule,
                 sync_team_memory, share_skill

        Args:
            action: Which learning operation
            subject: What was missed or what rule to create
            context: Action-specific parameters
        """
        ctx = context or {}

        if action == 'register_prevention_rule':
            return str(store.register_prevention_rule(
                rule_name=ctx.get('rule_name', subject[:50] if subject else 'unnamed'),
                trigger_event=ctx.get('trigger_event', 'tool.after:*'),
                check_query=ctx.get('check_query', subject),
                action_on_match=ctx.get('action_on_match', 'warn'),
                severity=ctx.get('severity', 'P1'),
            ))
        elif action == 'list_prevention_rules':
            rules = store.get_active_prevention_rules()
            return str(rules)
        elif action == 'delete_prevention_rule':
            rule_id = int(ctx.get('rule_id', 0))
            conn = store._connect()
            c = conn.cursor()
            c.execute("DELETE FROM prevention_rules WHERE id = ?", (rule_id,))
            conn.commit()
            return f"Deleted prevention rule #{rule_id}"
        elif action == 'record_missed_detection':
            return str(store.record_missed_detection(
                detection_type=ctx.get('detection_type', 'unknown'),
                description=subject or ctx.get('description', ''),
                suggested_fix=ctx.get('suggested_fix', ''),
            ))

        return f"Learn action '{action}' dispatched."

    # ═══════════════════════════════════════════════════════════
    # INTROSPECT — read-only system state (12 internal tools)
    # ═══════════════════════════════════════════════════════════

    @mcp.tool()
    def introspect(action: str, subject: str = "", context: dict = None) -> str:
        """System self-inspection: diagnostics, usage stats, autonomous status.

        Actions: autonomous_scan, self_diagnose, get_autonomous_status,
                 get_tool_usage_stats, browse_tool_usage,
                 get_injection_stats, get_prevention_stats

        Args:
            action: Which inspection to run
            subject: Optional filter or query
            context: Action-specific parameters
        """
        ctx = context or {}

        if action == 'autonomous_scan':
            return str(store.autonomous_scan())
        elif action == 'self_diagnose':
            return str(store.self_diagnose())
        elif action == 'get_autonomous_status':
            return str(store.get_autonomous_status())
        elif action == 'get_tool_usage_stats':
            return str(store.get_tool_usage_stats(
                days=int(ctx.get('days', 7))
            ))
        elif action == 'browse_tool_usage':
            return str(store.browse_tool_usage(
                tool_name=subject or ctx.get('tool_name', ''),
                limit=int(ctx.get('limit', 10)),
            ))
        elif action == 'get_injection_stats':
            return str(store.get_injection_prevention_rate())
        elif action == 'get_prevention_stats':
            rules = store.get_active_prevention_rules()
            return str({
                'total_rules': len(rules),
                'triggered': sum(1 for r in rules if r.get('times_triggered', 0) > 0),
            })
        # ── Round 2 introspect actions ──
        elif action == 'eval_harness':
            try:
                from core.eval.harness import EvalHarness
                harness = EvalHarness(store)
                report = harness.run()
                return json.dumps(report.summary(), indent=2)
            except Exception as e:
                return f"Eval harness error: {e}"
        elif action == 'health':
            try:
                from core.memory.integrity import IntegrityGuardian
                guardian = IntegrityGuardian(store)
                degradation = guardian.degradation_status()
                db_stats = guardian.db_stats()
                integrity = guardian.check_and_report()
                return json.dumps({
                    "degradation": degradation,
                    "db_stats": db_stats,
                    "integrity": integrity,
                }, indent=2)
            except Exception as e:
                return f"Health check error: {e}"
        elif action == 'cost_summary':
            days = int(ctx.get('days', 7))
            return json.dumps(store.get_cost_summary(days=days), indent=2)
        elif action == 'rule_lifecycle':
            return json.dumps(store.get_rule_lifecycle_summary(), indent=2)
        elif action == 'trigger_report':
            return json.dumps(store.get_trigger_report(), indent=2)

        return f"Introspect action '{action}' dispatched."

    logger.info("Verb tools registered", extra={"verbs": 7, "internal_tools": 66})
