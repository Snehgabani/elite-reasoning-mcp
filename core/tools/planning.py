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
    def sync_team_memory(
        remote_url: str = "http://localhost:8000",
        confirm: bool = False,
        direction: str = "pull",
    ) -> str:
        """Synchronize only through an explicitly approved team endpoint.

        Remote records are never promoted into anti-patterns or decisions
        automatically. They arrive as low-trust quarantined memory and require
        an explicit `elite_memory(action="approve")` review before use.

        Args:
            remote_url: Approved hub URL. Defaults to a local endpoint.
            confirm: Must be true before any network request is made.
            direction: `pull` (default), `push`, or `bidirectional`. Pushes
                also require `ELITE_SYNC_ALLOW_OUTBOUND=1`.
        """
        import getpass
        import json
        import os
        import tempfile
        from datetime import datetime, timedelta, timezone

        import httpx

        from core.privacy import redact_text, safe_error_detail
        from core.sync_security import authorize_manual_sync

        normalized_direction = direction.strip().lower()
        if normalized_direction not in {"pull", "push", "bidirectional"}:
            return "❌ direction must be pull, push, or bidirectional."

        configured_url = (
            os.environ.get("ELITE_SYNC_URL")
            or os.environ.get("TEAM_SYNC_URL")
            or remote_url
        )
        try:
            endpoint = authorize_manual_sync(configured_url, confirm)
        except (PermissionError, ValueError) as error:
            return f"❌ Sync access denied: {safe_error_detail(error)}"

        push_requested = normalized_direction in {"push", "bidirectional"}
        pull_requested = normalized_direction in {"pull", "bidirectional"}
        if push_requested and os.environ.get("ELITE_SYNC_ALLOW_OUTBOUND") != "1":
            return "❌ Outbound sync is disabled. Set ELITE_SYNC_ALLOW_OUTBOUND=1 after reviewing the data scope."

        user_id = os.environ.get("ELITE_USER_ID", getpass.getuser())
        headers = {}
        api_key = os.environ.get("ELITE_SYNC_API_KEY")
        if api_key:
            headers["X-Elite-Sync-Key"] = api_key

        cursor_path = os.path.join(store.brain_dir, "sync_cursor.json")
        last_pulled_at = None
        last_pushed_at = None
        if os.path.exists(cursor_path):
            try:
                with open(cursor_path, encoding="utf-8") as handle:
                    cursor = json.load(handle)
                if isinstance(cursor, dict):
                    # The v1 shared cursor used an incompatible ISO format and
                    # conflated pull and push state. Ignore it rather than risk
                    # silently dropping pre-upgrade local records.
                    last_pulled_at = cursor.get("last_pulled_at")
                    last_pushed_at = cursor.get("last_pushed_at")
            except (OSError, ValueError, TypeError):
                pass

        def canonical_cursor(value: object) -> str | None:
            if not isinstance(value, str) or not value:
                return None
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None

        last_pulled_at = canonical_cursor(last_pulled_at)
        last_pushed_at = canonical_cursor(last_pushed_at)

        def safe_records(records: list[dict]) -> list[dict]:
            sanitized: list[dict] = []
            for record in records[:200]:
                if not isinstance(record, dict):
                    continue
                item: dict[str, object] = {}
                for key, value in record.items():
                    if key == "id" or not isinstance(key, str):
                        continue
                    if isinstance(value, str):
                        item[key[:80]] = redact_text(value, limit=2000)
                    elif isinstance(value, (bool, int, float)) or value is None:
                        item[key[:80]] = value
                if item:
                    sanitized.append(item)
            return sanitized

        def write_cursor(pulled_at: str | None, pushed_at: str | None) -> None:
            fd, temporary_path = tempfile.mkstemp(prefix=".sync_cursor.", suffix=".tmp", dir=store.brain_dir)
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(
                        {
                            "version": 2,
                            "last_pulled_at": pulled_at,
                            "last_pushed_at": pushed_at,
                            "user_id": user_id,
                        },
                        handle,
                    )
                    handle.write("\n")
                os.replace(temporary_path, cursor_path)
                os.chmod(cursor_path, 0o600)
            except Exception:
                try:
                    os.unlink(temporary_path)
                except OSError:
                    pass
                raise

        quarantined = 0
        accepted = 0
        rejected = 0
        # Deliberately overlap one second because the legacy tables have only
        # second precision. The hub deduplicates re-sent records by content.
        operation_cursor = (datetime.now(timezone.utc) - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
        next_pulled_at = last_pulled_at
        next_pushed_at = last_pushed_at
        try:
            if pull_requested:
                params = {"user_id": user_id}
                if last_pulled_at:
                    params["since"] = last_pulled_at
                pull_response = httpx.get(
                    f"{endpoint}/api/sync/pull",
                    params=params,
                    headers=headers,
                    timeout=30.0,
                    follow_redirects=False,
                )
                pull_response.raise_for_status()
                remote_data = pull_response.json()
                if not isinstance(remote_data, dict):
                    return "❌ The approved sync hub returned an invalid payload."

                for key, memory_type in (
                    ("anti_patterns", "remote_anti_pattern"),
                    ("decisions", "remote_decision"),
                ):
                    records = remote_data.get(key, [])
                    if not isinstance(records, list):
                        continue
                    for record in safe_records(records):
                        store.record_memory_item(
                            memory_type=memory_type,
                            content=json.dumps(record, sort_keys=True),
                            scope="team",
                            source="remote_sync",
                            confidence=0.2,
                            trust_score=0.2,
                            privacy_class="internal",
                            tags="remote_sync,unverified",
                        )
                        quarantined += 1
                next_pulled_at = operation_cursor

            if push_requested:
                local_anti_patterns = safe_records(store.get_all_anti_patterns(since=last_pushed_at))
                local_decisions = safe_records(store.get_all_decisions(since=last_pushed_at))
                push_response = httpx.post(
                    f"{endpoint}/api/sync/push",
                    headers=headers,
                    json={
                        "user_id": user_id,
                        "anti_patterns": local_anti_patterns,
                        "decisions": local_decisions,
                    },
                    timeout=30.0,
                    follow_redirects=False,
                )
                push_response.raise_for_status()
                push_result = push_response.json()
                if not isinstance(push_result, dict):
                    return "❌ The approved sync hub returned an invalid push response."
                accepted = int(push_result.get("accepted", len(local_anti_patterns) + len(local_decisions)))
                rejected = int(push_result.get("rejected", 0))
                # Keep the outbound cursor unchanged after a partial reject so
                # the user can safely retry. The hub deduplicates accepted rows.
                if rejected == 0:
                    next_pushed_at = operation_cursor

            write_cursor(next_pulled_at, next_pushed_at)
            summary = [f"quarantined remote records: {quarantined}"] if pull_requested else []
            if push_requested:
                summary.append(f"outbound records: {accepted} accepted, {rejected} rejected")
            return "✅ Sync complete. " + "; ".join(summary) + ". Review remote memory before approval."
        except httpx.HTTPError as error:
            return f"❌ Sync failed safely: {safe_error_detail(error)}"
        except (OSError, ValueError, TypeError) as error:
            return f"❌ Sync failed safely: {safe_error_detail(error)}"
