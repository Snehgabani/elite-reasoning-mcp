def register(mcp, store, orchestrator=None):
    @mcp.tool()
    def get_elite_workflow(task_type: str) -> str:
        """TRIGGER: Call this when you are unsure how to tackle a task.
            Returns the exact sequence of Elite Prompts and Tools you should execute for a specific scenario.
            Args:
                task_type: What you are trying to do (e.g., 'debugging', 'planning', 'refactoring', 'incident', 'optimizing')
            """
        task_type = task_type.lower()
        if 'debug' in task_type or 'fix' in task_type:
            return "## Workflow: Debugging\n1. `five_whys` (Tool) - Drill to root cause (Ask 'Why?' 5 times).\n2. `check_anti_patterns` (Tool) - Has this happened before?\n3. Apply OODA Loop (Observe, Orient, Decide, Act) inline to fix the code.\n4. `record_mistake` (Tool) - Log the root cause and fix so it never happens again."
        elif 'plan' in task_type or 'architect' in task_type or 'design' in task_type:
            return "## Workflow: Architecture & Planning\n1. `check_anti_patterns` (Tool) - Avoid known pitfalls in this domain\n2. Inline: Apply First Principles (deconstruct assumptions) & MECE Analysis (map solution space without gaps).\n3. `adopt_vs_build` (Tool) - Prove we shouldn't adopt an existing library\n4. Inline: Apply Red Team Protocol (steel-man 3 counter-arguments to your own design).\n5. `bias_scan` (Tool) - Check your decision against cognitive biases\n6. `record_decision` (Tool) - Save the final architecture to the audit log."
        elif 'refactor' in task_type:
            return "## Workflow: Refactoring\n1. `smoke_test_gate` (Tool, action='create') - Capture the BEFORE state\n2. Inline: Apply Pre-Mortem (Imagine it fails catastrophically. Why? Mitigate.)\n3. `swiss_cheese_audit` (Tool) - Ensure no defensive layers are bypassed during the rewrite\n4. Write the code\n5. `smoke_test_gate` (Tool, action='complete') - Validate the AFTER state\n6. `record_quality_score` (Tool) - Grade the new codebase."
        elif 'incident' in task_type or 'outage' in task_type:
            return '## Workflow: Incident Response\n1. Inline: Apply SBAR (Situation, Background, Assessment, Recommendation) to structure the report.\n2. Inline: Apply OODA (Observe, Orient, Decide, Act) to rapidly iterate on fixes.\n3. `after_action_review` (Tool) - Once mitigated, conduct a blameless post-mortem.'
        elif 'optimiz' in task_type or 'improv' in task_type or 'performance' in task_type:
            return '## Workflow: Optimization\n1. `benchmark_track` (Tool) - Establish the current baseline\n2. Inline: Apply Scientific A/B Hypothesis (Define Hypothesis, Null Hypothesis, Test Design).\n3. Implement change\n4. `benchmark_track` (Tool) - Record the new value\n5. `record_decision` (Tool) - Document if the hypothesis was proven or rejected.'
        else:
            return '## Generic Elite Workflow\n1. `check_anti_patterns` (Tool) - Always check for past mistakes.\n2. Inline: Apply Inversion (What would guarantee failure?) and avoid those actions.\n3. Execute the task.\n4. `pre_commit_audit` (Tool) - Run the 6-pass quality check before finishing.'

    @mcp.tool()
    def check_anti_patterns(description: str) -> str:
        """TRIGGER: Call this BEFORE writing new code or designing a system.
            ⚠️ Searches for known mistakes matching your approach.
            Args:
                description: What you're about to build or the approach you're considering
            """
        results = store.check_anti_patterns(description)
        if not results:
            return '✅ No matching anti-patterns. Proceed with confidence.'
        out = f'⚠️ {len(results)} matching anti-patterns!\n\n'
        for r in results:
            out += f"### 🚨 [{r['severity'].upper()}] {r['mistake']}\n- Root Cause: {r['root_cause']}\n- Fix: {r['fix']}\n\n"
            
        # Semantic Compression: Token bounding to prevent context window overflow
        MAX_CHARS = 6000
        if len(out) > MAX_CHARS:
            out = out[:MAX_CHARS] + "\n\n...[TRUNCATED FOR CONTEXT WINDOW BUDGET: Refine your approach description to see more specific anti-patterns]..."
        return out

    @mcp.tool()
    def adopt_vs_build(capability: str, build_option: str='', adopt_option: str='') -> str:
        """TRIGGER: Call this EVERY TIME you consider writing a custom utility, component, or logic that might exist as a library.
            🏗️ Adopt vs Build — Rigorous build-vs-buy analysis accounting for hidden costs.
            Args:
                capability: What capability is needed
                build_option: Description of the build approach
                adopt_option: Description of the adopt/buy approach
            """
        return f"## 🏗️ Adopt vs Build Analysis\n### Capability Needed: {capability}\n\n| Factor | 🔨 Build{(' (' + build_option + ')' if build_option else '')} | 📦 Adopt{(' (' + adopt_option + ')' if adopt_option else '')} |\n|---|---|---|\n| **Time to first value** | _weeks/months_ | _hours/days_ |\n| **Upfront cost** | _dev hours × rate_ | _license/free_ |\n| **Ongoing maintenance** | _permanent (your team)_ | _shared (community/vendor)_ |\n| **Customizability** | 100% | _60-80%_ |\n| **Onboarding cost** | _docs, training, tribal knowledge_ | _existing docs/community_ |\n| **Bus factor risk** | _if creator leaves?_ | _community maintained_ |\n| **Security burden** | _you patch everything_ | _shared responsibility_ |\n| **Opportunity cost** | _what ELSE could team build?_ | _minimal_ |\n\n### Hidden Costs (often ignored)\n- [ ] Documentation you'll need to write\n- [ ] Tests you'll need to maintain\n- [ ] Edge cases you'll discover in production\n- [ ] Future developer onboarding time\n- [ ] Context switching from core product\n\n### Decision Framework\n- **BUILD if**: This is a CORE DIFFERENTIATOR and customizability gap blocks your product\n- **ADOPT if**: This is INFRASTRUCTURE and a good-enough solution exists\n- **IKEA Effect check**: Am I wanting to build because it's fun, not because it's strategic?\n\n### Verdict: BUILD / ADOPT / HYBRID\nRecord with `record_decision` for the audit trail."

    @mcp.tool()
    def set_goal(objective: str, key_results: str) -> str:
        """TRIGGER: Call this when starting a sprint or setting a major objective.
            🎯 Set an OKR-style goal with measurable key results.
            Args:
                objective: The qualitative, aspirational goal
                key_results: Comma-separated measurable key results
            """
        kr_list = [kr.strip() for kr in key_results.split(',') if kr.strip()]
        if not kr_list:
            return '❌ At least one key result is required.'
        goal_id = store.set_goal(objective, kr_list)
        out = f'🎯 Goal #{goal_id} set!\n\n**Objective**: {objective}\n\n**Key Results**:\n'
        for i, kr in enumerate(kr_list, 1):
            out += f'  {i}. {kr} — 0%\n'
        return out

    @mcp.tool()
    def check_goals() -> str:
        """TRIGGER: Call this to check progress on OKRs before starting daily work.
            🎯 View all active goals and their progress."""
        goals = store.get_active_goals()
        if not goals:
            return 'No active goals. Use set_goal to create one.'
        out = '## 🎯 Active Goals\n\n'
        for g in goals:
            bar_len = int(g['overall_pct'] / 5)
            bar = '█' * bar_len + '░' * (20 - bar_len)
            out += f"### #{g['id']}: {g['objective']}\n"
            out += f"Overall: [{bar}] {g['overall_pct']}%\n\n"
            for kr in g['key_results']:
                pct = g['progress'].get(kr, 0)
                out += f'  - {kr}: **{pct}%**\n'
            out += f"_Set: {g['created_at']} | Updated: {g['updated_at']}_\n\n"
        return out

    @mcp.tool()
    def update_goal(goal_id: int, key_result: str, progress: int) -> str:
        """Update progress on a specific key result of a goal.
            Args:
                goal_id: The ID of the goal to update
                key_result: The exact key result text to update
                progress: New progress percentage (0-100)
            """
        if not 0 <= progress <= 100:
            return '❌ Progress must be 0-100.'
        success = store.update_goal_progress(goal_id, key_result, progress)
        if success:
            return f'✅ Goal #{goal_id} key result updated to {progress}%.'
        return f'❌ Goal #{goal_id} not found or key result does not match.'

    @mcp.tool()
    def archive_goal(goal_id: int) -> str:
        """Archive a completed or stale goal, removing it from the active view.
            Args:
                goal_id: The ID of the goal to archive
            """
        success = store.archive_goal(goal_id)
        if success:
            return f'✅ Goal #{goal_id} archived.'
        return f'❌ Goal #{goal_id} not found.'

    @mcp.tool()
    def delete_goal(goal_id: int) -> str:
        """Permanently delete a goal (e.g., duplicates from stress tests).
            Args:
                goal_id: The ID of the goal to delete
            """
        success = store.delete_goal(goal_id)
        if success:
            return f'🗑️ Goal #{goal_id} deleted.'
        return f'❌ Goal #{goal_id} not found.'

    @mcp.tool()
    def resolve_prospective_failure(node_id: str, occurred: bool, evidence: str = '') -> str:
        """Resolve a prospective failure prediction as TRUE (it happened) or FALSE (prevented/impossible).
            Args:
                node_id: The exact node ID of the Prospective_Failure
                occurred: True if the failure happened, False if prevented
                evidence: Why this outcome was reached
            """
        try:
            store.graph.resolve_prediction(node_id, occurred)
            # Also update with evidence via resolve_hypothesis path
            if evidence:
                node = store.graph.get_node(node_id)
                if node:
                    import json
                    from datetime import datetime
                    props = node['properties']
                    props['evidence'] = evidence
                    props['evaluated_at'] = datetime.utcnow().isoformat()
                    conn = store.graph._get_conn()
                    try:
                        conn.execute("UPDATE graph_nodes SET properties = ? WHERE id = ?",
                                     (json.dumps(props), node_id))
                    finally:
                        store.graph._close(conn)
            status = "OCCURRED ⚠️" if occurred else "PREVENTED ✅"
            return f'{status} Prospective failure {node_id} resolved.'
        except Exception as e:
            return f'❌ Failed to resolve: {str(e)}'

    @mcp.tool()
    def sync_team_memory(remote_url: str = 'http://localhost:8000') -> str:
        """
        Perform a bi-directional sync of the Elite Memory database with the central team hub.
        Each user's contributions are tagged with their identity for attribution.
        Args:
            remote_url: The URL of the central sync server (default: http://localhost:8000)
        """
        import httpx
        import os
        import json
        import getpass
        from datetime import datetime

        # Override URL from env if available
        remote_url = os.environ.get("TEAM_SYNC_URL", remote_url)
        remote_url = remote_url.rstrip("/")

        # Identify this user
        user_id = os.environ.get("ELITE_USER_ID", getpass.getuser())

        headers = {}
        api_key = os.environ.get("ELITE_SYNC_API_KEY")
        if api_key:
            headers["X-Elite-Sync-Key"] = api_key

        cursor_path = os.path.join(store.brain_dir, "sync_cursor.json")
        last_synced_at = None
        if os.path.exists(cursor_path):
            try:
                with open(cursor_path, 'r') as f:
                    last_synced_at = json.load(f).get("last_synced_at")
            except Exception:
                pass

        try:
            # 0. REGISTER this user with the hub (idempotent)
            from core.tools.orchestration import scan_available_mcps, scan_available_skills
            try:
                httpx.post(
                    f"{remote_url}/api/users/register",
                    headers=headers,
                    json={
                        "user_id": user_id,
                        "display_name": user_id,
                        "ide_type": "antigravity",
                        "mcp_count": len(scan_available_mcps()),
                        "skill_count": len(scan_available_skills()),
                    },
                    timeout=5.0,
                )
            except Exception:
                pass  # Registration is best-effort

            # 1. PULL from remote
            pull_url = f"{remote_url}/api/sync/pull"
            pull_params = {"user_id": user_id}
            if last_synced_at:
                pull_params["since"] = last_synced_at
            pull_resp = httpx.get(pull_url, params=pull_params, headers=headers, timeout=30.0)
            pull_resp.raise_for_status()
            remote_data = pull_resp.json()
            
            # Merge remote into local
            existing_aps = {ap['mistake'] for ap in store.get_all_anti_patterns()}
            added_aps = 0
            for ap in remote_data.get('anti_patterns', []):
                if ap['mistake'] not in existing_aps:
                    store.record_mistake(
                        mistake=ap.get('mistake', ''),
                        root_cause=ap.get('root_cause', ''),
                        fix=ap.get('fix', ''),
                        severity=ap.get('severity', 'medium'),
                        tags=ap.get('tags', '')
                    )
                    added_aps += 1

            existing_decs = {d['decision'] for d in store.get_all_decisions()}
            added_decs = 0
            for d in remote_data.get('decisions', []):
                if d['decision'] not in existing_decs:
                    store.record_decision(
                        context=d.get('context', ''),
                        decision=d.get('decision', ''),
                        rationale=d.get('rationale', '')
                    )
                    added_decs += 1

            # 2. PUSH local to remote (with user_id)
            local_aps = store.get_all_anti_patterns(since=last_synced_at)
            local_decs = store.get_all_decisions(since=last_synced_at)
            local_payload = {
                "user_id": user_id,
                "anti_patterns": local_aps,
                "decisions": local_decs
            }
            push_resp = httpx.post(f"{remote_url}/api/sync/push", headers=headers, json=local_payload, timeout=30.0)
            push_resp.raise_for_status()
            push_res = push_resp.json()

            accepted = push_res.get("accepted", len(local_aps) + len(local_decs))
            rejected = push_res.get("rejected", 0)
            total_users = push_res.get("total_users", "?")

            # Update cursor
            new_cursor_time = datetime.utcnow().isoformat()
            with open(cursor_path, 'w') as f:
                json.dump({"last_synced_at": new_cursor_time, "user_id": user_id}, f)
            
            return f"✅ Sync Complete (user: {user_id})! Pulled {added_aps} anti-patterns and {added_decs} decisions. Pushed: {accepted} accepted, {rejected} rejected. Team size: {total_users} users."
        except Exception as e:
            return f"❌ Sync Failed: {str(e)}"

