

def register(mcp, store, orchestrator=None):
    @mcp.tool()
    def record_prompt_intent(session_id: str, prompt_text: str,
                             intent_category: str = 'unknown',
                             reasoning_type: str = 'unknown',
                             implicit_expectation: str = '',
                             failure_detected: str = '') -> str:
        """TRIGGER: Call this on EVERY user prompt to classify intent and detect reasoning type.
            🧠 Records the prompt with extracted intent for adaptive learning.
            Args:
                session_id: Current session/conversation ID
                prompt_text: The user's prompt text
                intent_category: Classified intent (e.g., 'feature_request', 'debugging', 'clarification')
                reasoning_type: Detected reasoning type (e.g., 'loop_kick', 'gap_injection', 'depth_escalation', 'substantive')
                implicit_expectation: What the user implicitly expects but didn't say
                failure_detected: Description of any failure detected in this prompt
        """
        row_id = store.record_prompt_intent(
            session_id, prompt_text, intent_category, reasoning_type,
            implicit_expectation, failure_detected
        )
        return f'🧠 Prompt #{row_id} recorded (intent: {intent_category}, reasoning: {reasoning_type})'

    @mcp.tool()
    def analyze_prompt_sequence(session_id: str = '', limit: int = 20) -> str:
        """TRIGGER: Call this periodically to detect meta-patterns in user prompts.
            📊 Analyzes recent prompts for loop failures, anticipation gaps, and depth rejections.
            Args:
                session_id: Optional session ID to filter by (empty = all sessions)
                limit: Number of recent prompts to analyze (default: 20)
        """
        result = store.analyze_prompt_sequence(session_id, limit)
        if result['health'] == 'no_data':
            return '📊 No prompt data yet. Prompts will be analyzed as they are recorded.'

        out = "## 📊 Prompt Sequence Analysis\n\n"
        out += f"**Health Score**: {result['health_score']}/100 ({result['health'].upper()})\n"
        out += f"**Total Prompts**: {result['total_prompts']} ({result['substantive_prompts']} substantive, {result['waste_prompts']} waste)\n"
        out += f"**Detection Failures**: {result['detection_failures']}\n\n"

        if result['patterns']:
            out += "### Detected Patterns\n\n"
            for p in result['patterns']:
                out += f"- **{p['type']}**: {p['count']} occurrences ({p['pct']}%)\n"
                out += f"  → Fix: {p['fix']}\n"
        else:
            out += "✅ No failure patterns detected.\n"

        return out

    @mcp.tool()
    def get_user_thinking_model() -> str:
        """TRIGGER: Call this to understand how the user thinks and what adaptations have been learned.
            🧠 Returns the current model of user thinking patterns with confidence scores.
        """
        patterns = store.get_user_thinking_model()
        if not patterns:
            return '🧠 No thinking patterns learned yet. Patterns emerge as prompts are analyzed.'

        out = "## 🧠 User Thinking Model\n\n"
        out += "| Pattern | Evidence | Confidence | Adaptation |\n"
        out += "|---|---|---|---|\n"
        for p in patterns:
            conf_bar = '█' * int(p['confidence'] * 10) + '░' * (10 - int(p['confidence'] * 10))
            out += f"| {p['pattern']} | {p['evidence']} observations | [{conf_bar}] {p['confidence']:.2f} | {p['adaptation']} |\n"
        out += f"\n_Total patterns: {len(patterns)}_"
        return out

    @mcp.tool()
    def update_thinking_pattern(pattern_name: str, system_adaptation: str,
                                example_prompt: str = '') -> str:
        """TRIGGER: Call this when you detect a recurring user thinking pattern.
            🧠 Updates or creates a user thinking pattern with system adaptation.
            Args:
                pattern_name: Name of the thinking pattern (e.g., 'prefers_depth_over_breadth')
                system_adaptation: How the system should adapt (e.g., 'Always provide implementation details')
                example_prompt: Optional example prompt that triggered this pattern
        """
        result = store.update_thinking_pattern(pattern_name, system_adaptation, example_prompt)
        return f'🧠 {result}'

    @mcp.tool()
    def autonomous_scan() -> str:
        """TRIGGER: Call this periodically or when the system seems to be underperforming.
            🔍 Runs the autonomous gap detector across all subsystems.
            Checks: missed detections, stale goals, quality regression, expired predictions, prompt health, rule effectiveness.
        """
        result = store.autonomous_scan()
        out = "## 🔍 Autonomous Gap Scan\n\n"
        out += f"**Total Gaps**: {result['total_gaps']} (P0: {result['p0_count']}, P1: {result['p1_count']}, P2: {result['p2_count']})\n"
        out += f"**Scan Time**: {result['scan_time']}\n\n"

        if not result['gaps']:
            out += "✅ No gaps detected. System is healthy.\n"
        else:
            for g in result['gaps']:
                severity_emoji = {'P0': '🔴', 'P1': '🟡', 'P2': '🔵'}.get(g['severity'], '⚪')
                out += f"### {severity_emoji} [{g['severity']}] {g['source']}\n"
                out += f"- **Detail**: {g['detail']}\n"
                out += f"- **Action**: {g['action']}\n"
                out += f"- **Auto-executable**: {'Yes' if g.get('auto_executable') else 'No'}\n\n"

        return out

    @mcp.tool()
    def register_prevention_rule(rule_name: str, trigger_event: str,
                                 check_query: str, action_on_match: str,
                                 severity: str = 'P1',
                                 source_detection_id: int = 0) -> str:
        """TRIGGER: Call this to convert a missed detection into an automated prevention rule.
            🛡️ Registers an automated check that fires on a trigger event.
            Args:
                rule_name: Unique name for the rule
                trigger_event: Event that triggers the check (e.g., 'pre_commit', 'prompt_received', 'tool_invoked')
                check_query: What to check when triggered
                action_on_match: What to do if the check matches
                severity: P0/P1/P2
                source_detection_id: ID of the missed detection this rule was derived from (0 = manual)
        """
        src_id = source_detection_id if source_detection_id > 0 else None
        result = store.register_prevention_rule(
            rule_name, trigger_event, check_query, action_on_match,
            severity, src_id
        )
        return f'🛡️ {result}'

    @mcp.tool()
    def self_diagnose() -> str:
        """TRIGGER: Call this for a full health check of the adaptive learning system.
            🏥 Runs a complete diagnostic covering prevention rules, prompt intelligence, missed detections, tool usage, and autonomy rate.
        """
        result = store.self_diagnose()
        out = "## 🏥 Adaptive Learning System Diagnostic\n\n"
        out += f"**Health**: {result['health'].upper()}\n"
        out += f"**Autonomy Rate**: {result['autonomy_rate']}%\n"
        out += f"**Diagnosed**: {result['diagnosed_at']}\n\n"

        out += "### Subsystem Status\n\n"
        out += "| Subsystem | Metric | Value |\n"
        out += "|---|---|---|\n"
        out += f"| Prevention Rules | Active | {result['prevention_rules']['active']} |\n"
        out += f"| Prevention Rules | Total Triggers | {result['prevention_rules']['total_triggers']} |\n"
        out += f"| Prompt Intelligence | Total Prompts | {result['prompt_intelligence']['total_prompts']} |\n"
        out += f"| Prompt Intelligence | Patterns Learned | {result['prompt_intelligence']['patterns_learned']} |\n"
        out += f"| Missed Detections | Total | {result['missed_detections']['total']} |\n"
        out += f"| Missed Detections | Automated | {result['missed_detections']['automated']} |\n"
        out += f"| Missed Detections | Pending | {result['missed_detections']['pending']} |\n"
        out += f"| Tool Usage | Unique Tools | {result['tool_usage']['unique_tools']} |\n"
        out += f"| Tool Usage | Total Calls | {result['tool_usage']['total_calls']} |\n"

        return out

    @mcp.tool()
    def generate_autonomous_goals() -> str:
        """TRIGGER: Call this to generate prioritized goals from learned patterns.
            🎯 Analyzes missed detections, quality trends, and prompt patterns to create autonomous improvement goals.
        """
        goals = store.generate_autonomous_goals()
        if not goals:
            return '🎯 No autonomous goals generated. The system is operating within expected parameters.'

        out = "## 🎯 Autonomous Goals\n\n"
        for i, g in enumerate(goals, 1):
            priority_emoji = {'P0': '🔴', 'P1': '🟡', 'P2': '🔵'}.get(g['priority'], '⚪')
            out += f"### {i}. {priority_emoji} [{g['priority']}] {g['objective']}\n"
            out += f"- **Source**: {g['source']}\n"
            out += f"- **Confidence**: {g['confidence']:.0%}\n"
            out += f"- **Auto-executable**: {'Yes' if g.get('auto_executable') else 'No'}\n\n"

        return out

    @mcp.tool()
    def get_autonomous_status() -> str:
        """TRIGGER: Call this for a complete view of what the adaptive learning system is doing autonomously.
            📋 Returns full status: diagnosis, autonomous goals, and gap scan results.
        """
        result = store.get_autonomous_status()
        out = "## 📋 Autonomous Status Report\n\n"
        out += f"**Summary**: {result['summary']}\n\n"

        # Inline the diagnosis
        diag = result['diagnosis']
        out += f"### Health: {diag['health'].upper()} (Autonomy: {diag['autonomy_rate']}%)\n\n"

        # Goals
        goals = result['autonomous_goals']
        if goals:
            out += f"### {len(goals)} Autonomous Goals\n\n"
            for g in goals:
                priority_emoji = {'P0': '🔴', 'P1': '🟡', 'P2': '🔵'}.get(g['priority'], '⚪')
                out += f"- {priority_emoji} [{g['priority']}] {g['objective']} ({g['confidence']:.0%})\n"
            out += "\n"

        # Gaps
        scan = result['gap_scan']
        if scan['total_gaps'] > 0:
            out += f"### {scan['total_gaps']} Gaps Detected\n\n"
            for g in scan['gaps']:
                severity_emoji = {'P0': '🔴', 'P1': '🟡', 'P2': '🔵'}.get(g['severity'], '⚪')
                out += f"- {severity_emoji} [{g['severity']}] {g['detail']}\n"
        else:
            out += "### ✅ No Gaps Detected\n"

        return out

    @mcp.tool()
    def get_tool_usage_stats(days: int = 7) -> str:
        """TRIGGER: Call this to review tool usage analytics.
            📈 Returns tool usage statistics for the specified period.
            Args:
                days: Number of days to analyze (default: 7)
        """
        result = store.get_tool_usage_stats(days)
        out = f"## 📈 Tool Usage Stats ({result['period_days']} days)\n\n"
        out += f"**Total Invocations**: {result['total_invocations']}\n\n"

        if result['by_tool']:
            out += "| Tool | Invocations |\n"
            out += "|---|---|\n"
            for tool, count in result['by_tool'].items():
                out += f"| {tool} | {count} |\n"
            out += f"\n**Most Used**: {', '.join(result['most_used'])}\n"
        else:
            out += "No tool usage recorded in this period.\n"

        return out

    @mcp.tool()
    def list_prevention_rules(trigger_event: str = '') -> str:
        """TRIGGER: Call this to see all active prevention rules and their fire counts.
            🛡️ Lists rules, optionally filtered by trigger event.
            Args:
                trigger_event: Optional filter (e.g., 'on_prompt', 'after_tool_call'). Empty = all.
        """
        rules = store.get_active_prevention_rules(trigger_event)
        if not rules:
            return '🛡️ No prevention rules found.' + (f' (filter: {trigger_event})' if trigger_event else '')

        out = "## 🛡️ Prevention Rules\n\n"
        out += "| Rule | Trigger | Severity | Fired | Check |\n"
        out += "|---|---|---|---|---|\n"
        for r in rules:
            out += (
                f"| {r['rule_name']} | {r['trigger_event']} | {r['severity']} | "
                f"{r['times_triggered']}x | {r['check_query'][:60]}... |\n"
            )
        out += f"\n_Total: {len(rules)} rules_"
        return out

    @mcp.tool()
    def delete_prevention_rule(rule_name: str) -> str:
        """Delete a prevention rule by name.
            🗑️ Removes a rule from the active set. Use when a rule is causing false positives.
            Args:
                rule_name: Exact name of the rule to delete.
        """
        conn = store._connect()
        c = conn.cursor()
        c.execute("DELETE FROM prevention_rules WHERE rule_name = ?", (rule_name,))
        deleted = c.rowcount
        store._close(conn)
        if deleted:
            return f'🗑️ Rule `{rule_name}` deleted.'
        return f'❌ Rule `{rule_name}` not found.'

    @mcp.tool()
    def predictive_prevention(limit: int = 5) -> str:
        """TRIGGER: Call this to see predicted failures based on pattern analysis.
            🔮 Analyzes anti-patterns, quality trends, and missed detections to predict likely failures.
            Args:
                limit: Number of predictions to generate (default: 5)
        """
        predictions = []

        # 1. Recurring severity patterns
        patterns = store.get_all_anti_patterns(limit=50)
        severity_counts = {}
        for p in patterns:
            sev = p.get('severity', 'medium')
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        if severity_counts.get('high', 0) + severity_counts.get('critical', 0) > 3:
            predictions.append({
                'prediction': 'High-severity mistakes are recurring — systemic root cause likely',
                'confidence': min(0.9, (severity_counts.get('high', 0) + severity_counts.get('critical', 0)) * 0.15),
                'action': 'Run root-cause analysis on all high/critical mistakes to find shared patterns',
                'source': 'anti_pattern_analysis'
            })

        # 2. Quality trend decline
        trend = store.get_quality_trend(20)
        if trend.get('trend') == 'declining':
            predictions.append({
                'prediction': f"Quality is declining (avg: {trend.get('average', 0):.1f})",
                'confidence': 0.8,
                'action': 'Investigate recent changes causing quality regression',
                'source': 'quality_trend'
            })

        # 3. Prompt health degradation
        prompt_analysis = store.analyze_prompt_sequence(limit=20)
        if prompt_analysis.get('health_score', 100) < 50:
            predictions.append({
                'prediction': f"User frustration rising — health score {prompt_analysis.get('health_score', 0)}/100",
                'confidence': 0.85,
                'action': 'Review recent prompt patterns for unaddressed user needs',
                'source': 'prompt_analysis'
            })

        # 4. Unautomated detections accumulating
        unautomated = store.get_unautomated_detections()
        if len(unautomated) >= 3:
            predictions.append({
                'prediction': f"{len(unautomated)} missed detections still not automated — same failures will recur",
                'confidence': 0.9,
                'action': 'Convert top missed detections to prevention rules immediately',
                'source': 'missed_detections'
            })

        # 5. Stale goals
        goals = store.get_active_goals()
        for g in goals:
            if g.get('overall_pct', 0) < 10:
                predictions.append({
                    'prediction': f"Goal '{g['objective'][:50]}' is stale (progress: {g.get('overall_pct', 0):.0f}%)",
                    'confidence': 0.7,
                    'action': 'Either make progress or archive the goal',
                    'source': 'goal_staleness'
                })

        predictions = predictions[:limit]

        if not predictions:
            return '🔮 No failure predictions generated. System patterns look healthy.'

        out = "## 🔮 Predictive Prevention\n\n"
        for i, p in enumerate(predictions, 1):
            conf_bar = '█' * int(p['confidence'] * 10) + '░' * (10 - int(p['confidence'] * 10))
            out += f"### {i}. {p['prediction']}\n"
            out += f"- **Confidence**: [{conf_bar}] {p['confidence']:.0%}\n"
            out += f"- **Recommended Action**: {p['action']}\n"
            out += f"- **Source**: {p['source']}\n\n"

        return out

