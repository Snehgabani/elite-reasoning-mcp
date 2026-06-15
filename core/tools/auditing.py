def register(mcp, store, orchestrator=None):
    def _auto_update_goals(store, work_description: str) -> str:
        """Gap #4 fix: Auto-scan active goals and increment progress when work matches a key result."""
        try:
            goals = store.get_goals()
            updates = []
            work_lower = work_description.lower()
            for g in goals:
                for kr in g.get("key_results", []):
                    kr_text = kr.get("description", "").lower()
                    kr_progress = kr.get("progress", 0)
                    if kr_progress >= 100:
                        continue
                    # Fuzzy match: if 3+ words from the key result appear in the work description
                    kr_words = set(kr_text.split())
                    work_words = set(work_lower.split())
                    overlap = kr_words & work_words
                    if len(overlap) >= 3:
                        try:
                            store.update_goal(g["id"], kr.get("description", ""), min(kr_progress + 25, 100))
                            updates.append(f"Goal #{g['id']} key result auto-advanced")
                        except Exception:
                            pass
            if updates:
                return " | " + " | ".join(updates)
        except Exception:
            pass
        return ""

    @mcp.tool()
    def record_mistake(mistake: str, root_cause: str, fix: str, severity: str='medium', tags: str='') -> str:
        """TRIGGER: Call this EVERY TIME you resolve a bug or make a mistake.
            🛡️ Record a mistake so it NEVER happens again. The immune system gets stronger with every failure.
            Args:
                mistake: What went wrong
                root_cause: WHY it went wrong
                fix: How it was fixed
                severity: low/medium/high/critical
                tags: Comma-separated tags
            """
        row_id = store.record_mistake(mistake, root_cause, fix, severity, tags)
        total = store.count_anti_patterns()
        goal_msg = _auto_update_goals(store, f"{mistake} {root_cause} {fix}")
        return f'🛡️ Anti-pattern #{row_id} recorded ({severity}). Immune system: {total} entries.{goal_msg}'

    @mcp.tool()
    def record_decision(decision: str, rationale: str, alternatives_rejected: str='', context: str='') -> str:
        """TRIGGER: Call this EVERY TIME you make a consequential architectural or technical choice.
            📝 Record an architectural decision with full rationale. Creates searchable audit trail.
            Args:
                decision: What was decided
                rationale: WHY
                alternatives_rejected: What was considered and rejected
                context: Circumstances
            """
        row_id = store.record_decision(decision, rationale, alternatives_rejected, context)
        goal_msg = _auto_update_goals(store, f"{decision} {rationale}")
        return f'📝 Decision #{row_id} recorded and indexed.{goal_msg}'


    @mcp.tool()
    def search_decisions(query: str) -> str:
        """TRIGGER: Call this when you need context on WHY a certain technology or pattern is used in this codebase.
            🔍 Search past decisions for precedent or conflict.
            Args:
                query: What to search for
            """
        results = store.search_decisions(query)
        if not results:
            return 'No matching past decisions. This is a new decision area.'
        out = f'Found {len(results)} relevant decisions:\n\n'
        for d in results:
            out += f"### 📝 {d['decision']}\n- Rationale: {d['rationale']}\n"
            if d['alternatives_rejected']:
                out += f"- Rejected: {d['alternatives_rejected']}\n"
            out += f"- _Decided: {d['created_at']}_\n\n"

        # Semantic Compression: Token bounding to prevent context window overflow
        MAX_CHARS = 6000
        if len(out) > MAX_CHARS:
            out = out[:MAX_CHARS] + "\n\n...[TRUNCATED FOR CONTEXT WINDOW BUDGET: Use more specific queries to find older decisions]..."
        return out

    @mcp.tool()
    def record_quality_score(score: int, dimension: str='overall', notes: str='') -> str:
        """TRIGGER: Call this when finishing a major component to grade the output.
            📊 Record quality score (0-100). Tracks improvement over time.
            Args:
                score: 0-100
                dimension: One of: test_pass_rate, tool_availability, sync_latency, dedup_effectiveness, security, performance, readability, overall
                notes: What was scored and HOW (must include measurement method)
            """
        if not 0 <= score <= 100:
            return '❌ Score must be 0-100.'

        # Gap #7: Enforce concrete dimensions
        VALID_DIMENSIONS = {
            "test_pass_rate", "tool_availability", "sync_latency",
            "dedup_effectiveness", "security", "performance",
            "readability", "overall"
        }
        if dimension not in VALID_DIMENSIONS:
            return f"❌ Invalid dimension `{dimension}`. Use one of: {', '.join(sorted(VALID_DIMENSIONS))}"

        warning = ""
        if dimension == "overall" and not notes:
            warning = "\n⚠️ 'overall' without notes is a vanity metric. Specify HOW you measured this."

        store.record_quality_score(score, dimension, notes)
        t = store.get_quality_trend()
        return f"📊 {score}/100 ({dimension}) recorded. Avg: {t['average']}/100. Trend: {t['trend']}.{warning}"

    @mcp.tool()
    def get_quality_trend() -> str:
        """TRIGGER: Call this to check if the team's output quality is improving or declining over time.
            📊 Quality trend dashboard with per-dimension breakdown."""
        t = store.get_quality_trend()
        if t['trend'] == 'no_data':
            return 'No quality data yet.'

        # Build per-dimension breakdown
        dimensions = {}
        for s in t.get("scores", []):
            dim = s.get("dimension", "overall")
            if dim not in dimensions:
                dimensions[dim] = []
            dimensions[dim].append(s.get("score", 0))

        breakdown = ""
        if dimensions:
            breakdown = "\n\n**Per-Dimension:**\n| Dimension | Avg | Count | Latest |\n|---|---|---|---|\n"
            for dim, scores in sorted(dimensions.items()):
                avg = sum(scores) / len(scores)
                breakdown += f"| {dim} | {avg:.0f}/100 | {len(scores)} | {scores[-1]}/100 |\n"

        return f"📊 Average: **{t['average']}/100** | Latest: **{t['latest']}/100** | Trend: **{t['trend'].upper()}** | Points: {t['count']}{breakdown}"


    @mcp.tool()
    def pre_commit_audit(diff_summary: str) -> str:
        """TRIGGER: Call this EXACTLY ONCE right before pushing code or calling a task 'done'.
            🔍 6-pass structured audit on code changes before committing. Cross-references anti-patterns.
            Args:
                diff_summary: Description of the code changes
            """
        matches = store.check_anti_patterns(diff_summary)
        t = f'## 🔍 Pre-Commit Elite Audit\n\n### Changes: {diff_summary}\n\n### Pass 1: Security\n- [ ] No hardcoded secrets/keys  - [ ] No injection vulnerabilities  - [ ] Auth enforced  - [ ] Inputs validated\n\n### Pass 2: Error Handling\n- [ ] Async try/catch  - [ ] Errors logged with context  - [ ] Edge cases handled\n\n### Pass 3: Performance\n- [ ] No N+1 queries  - [ ] No memory leaks  - [ ] Large data paginated\n\n### Pass 4: Tests\n- [ ] New logic tested  - [ ] Edge cases tested  - [ ] Error paths tested\n\n### Pass 5: API Contract\n- [ ] No breaking changes  - [ ] New endpoints documented\n\n### Pass 6: Anti-Pattern Cross-Reference\n'
        if matches:
            t += f'⚠️ **{len(matches)} matching anti-patterns!**\n'
            for ap in matches:
                t += f"- 🚨 [{ap['severity'].upper()}] {ap['mistake']} → Fix: {ap['fix']}\n"
        else:
            t += '✅ No matching anti-patterns.\n'
        t += '\n### Verdict: PASS / CONDITIONAL PASS / BLOCK'
        return t

    @mcp.tool()
    def swiss_cheese_audit(change_description: str, layers: str='') -> str:
        """TRIGGER: Call this when making changes to critical paths (auth, payments, data destruction).
            🧀 Swiss Cheese Model — Analyze layered defenses for aligned holes. From aviation/nuclear safety.
            Args:
                change_description: What change is being made
                layers: Optional comma-separated custom layers (default: standard 6-layer defense)
            """
        if layers:
            layer_list = [l.strip() for l in layers.split(',')]
        else:
            layer_list = ['Type System / Static Analysis', 'Unit Tests', 'Code Review', 'Integration / Contract Tests', 'Staging / Pre-prod Validation', 'Production Monitoring / Alerting']
        return f'## 🧀 Swiss Cheese Model Audit\n### Change: {change_description}\n\nFor each defense layer, identify if a "hole" exists that this change could slip through:\n\n| # | Defense Layer | Status | Hole Description | Mitigation |\n|---|---|---|---|---|\n' + '\n'.join([f'| {i + 1} | {l} | ✅ Solid / ⚠️ Hole / ❌ Missing | _describe_ | _action_ |' for i, l in enumerate(layer_list)]) + "\n\n### Alignment Analysis\n- **Aligned holes**: List any chains of 2+ consecutive holes\n- **Critical path**: Could a defect pass through ALL layers?\n- **Verdict**: SAFE (no alignment) / AT RISK (partial alignment) / CRITICAL (full alignment)\n\n### Recommended Actions\nFor each hole, specify the MINIMUM action to break the alignment.\nPriority: Fix the cheapest hole in any aligned chain first.\n\n_Remember: You don't need perfect layers. You need NO aligned holes._"

    @mcp.tool()
    def bias_scan(decision_description: str) -> str:
        """TRIGGER: Call this BEFORE finalizing any architectural decision or adopting a new technology.
            🧠 Cognitive Bias Scanner — Check 12 biases against a decision.
            Args:
                decision_description: The decision or recommendation being evaluated
            """
        return f"## 🧠 Cognitive Bias Scan\n### Decision: {decision_description}\n\nEvaluate this decision against each bias. Mark ✅ (clear) or ⚠️ (detected):\n\n| # | Bias | Check Question | Status |\n|---|---|---|---|\n| 1 | **Confirmation** | Did I actively seek CONTRADICTING evidence? | ✅/⚠️ |\n| 2 | **Anchoring** | Am I fixated on the first solution I considered? | ✅/⚠️ |\n| 3 | **Availability** | Am I overweighting a RECENT experience? | ✅/⚠️ |\n| 4 | **Sunk Cost** | Am I continuing because of TIME already invested? | ✅/⚠️ |\n| 5 | **Bandwagon** | Am I choosing this because it's POPULAR? | ✅/⚠️ |\n| 6 | **Dunning-Kruger** | Am I overestimating my EXPERTISE in this domain? | ✅/⚠️ |\n| 7 | **Optimism** | Am I underestimating RISKS and overestimating benefits? | ✅/⚠️ |\n| 8 | **Status Quo** | Am I avoiding change just because current state is familiar? | ✅/⚠️ |\n| 9 | **Survivorship** | Am I only looking at SUCCESSES and ignoring failures? | ✅/⚠️ |\n| 10 | **Framing** | Would I decide differently if the problem were FRAMED differently? | ✅/⚠️ |\n| 11 | **Planning Fallacy** | Are my time/effort estimates based on BEST case? | ✅/⚠️ |\n| 12 | **IKEA Effect** | Am I overvaluing this because I BUILT it myself? | ✅/⚠️ |\n\n### Summary\n- Biases detected: [count]\n- Highest risk bias: [which one and why]\n- Debiasing action: [specific step to counter the top bias]\n\n### Revised Decision (if needed)\nAfter debiasing, does the original decision still hold?"

    @mcp.tool()
    def benchmark_track(metric: str, value: float=0, unit: str='', action: str='record', context: str='') -> str:
        """TRIGGER: Call this whenever making performance improvements to track the delta.
            📈 Benchmark Tracker — SPC-style baseline & delta tracking with statistical control limits.
            Args:
                metric: Name of the metric (e.g., 'build_time', 'test_pass_rate', 'bundle_size')
                value: The measured value (required for 'record' action)
                unit: Unit of measurement
                action: 'record' to add a data point, 'trend' to view the trend, 'list' to see all metrics
                context: Additional context
            """
        if action == 'list':
            metrics = store.list_benchmark_metrics()
            if not metrics:
                return "No benchmarks recorded yet. Use action='record' to start tracking."
            return '📈 Tracked Metrics:\n' + '\n'.join([f'- {m}' for m in metrics])
        if action == 'trend':
            t = store.get_benchmark_trend(metric)
            if t['status'] == 'no_data':
                return f"No data for metric '{metric}'."
            status_emoji = {'in_control': '✅', 'above_control_limit': '🔴', 'below_control_limit': '🔴'}.get(t['status'], '⚠️')
            return f"📈 **{metric}** ({t['unit']})\n- Latest: **{t['latest']}** | Baseline: {t['baseline']} | Δ: {t['delta_pct']:+.1f}%\n- Average: {t['average']} ± {t['stdev']} (n={t['count']})\n- Control: [{t['lcl']}, {t['ucl']}]\n- Status: {status_emoji} **{t['status'].upper().replace('_', ' ')}**"
        store.record_benchmark(metric, value, unit, context)
        t = store.get_benchmark_trend(metric)
        status_emoji = {'in_control': '✅', 'above_control_limit': '🔴', 'below_control_limit': '🔴'}.get(t['status'], '⚠️')
        return f"📈 {metric}: {value} {unit} recorded. {status_emoji} Status: {t['status'].upper().replace('_', ' ')} (avg: {t['average']}, n={t['count']})"

    @mcp.tool()
    def record_prospective_failure(action: str, predicted_failure: str, trigger_condition: str) -> str:
        """
        Record a simulated future failure mode into the graph.
        Args:
            action: The proposed action that could lead to this failure.
            predicted_failure: The specific catastrophic outcome predicted.
            trigger_condition: The exact condition that would confirm this failure occurred.
        """
        try:
            node_id = store.graph.add_prospective_failure(action, predicted_failure, trigger_condition)
            return f"✅ Prospective Failure recorded with Node ID: {node_id}. State is UNRESOLVED."
        except Exception as e:
            return f"❌ Failed to record prospective failure: {str(e)}"

    @mcp.tool()
    def validate_predictions(current_state_summary: str) -> str:
        """
        Fetch all unresolved predictions and validate them against the current state.
        Args:
            current_state_summary: A summary of the current reality/system state to test predictions against.
        """
        try:
            unresolved = store.graph.get_unresolved_predictions()
            if not unresolved:
                return "✅ No unresolved predictions to validate."

            out = f"## 🔮 Prediction Validation Engine\n\nI found {len(unresolved)} unresolved prediction(s). Please evaluate them against the current state.\n\n"
            out += f"**Current State Summary:** {current_state_summary}\n\n"

            for p in unresolved:
                props = p['properties']
                out += f"### Prediction [{p['id']}]\n"
                out += f"- **Action Taken:** {props.get('action')}\n"
                out += f"- **Predicted Failure:** {props.get('predicted_failure')}\n"
                out += f"- **Trigger Condition:** {props.get('trigger_condition')}\n"
                out += "-> *Task: Evaluate if this trigger condition has been met. If YES, call `resolve_prediction(occurred=true)` and generate an anti-pattern. If NO, do nothing or resolve as FALSE if you know it cannot happen anymore.*\n\n"

            return out
        except Exception as e:
            return f"❌ Failed to fetch predictions: {str(e)}"
