def register(mcp, store, orchestrator=None):
    @mcp.tool()
    def check_anti_patterns(description: str) -> str:
        """TRIGGER: Call this BEFORE writing new code or designing a system.
        ⚠️ Searches for known mistakes matching your approach.
        Args:
            description: What you're about to build or the approach you're considering
        """
        results = store.check_anti_patterns(description)
        if not results:
            return "✅ No matching anti-patterns. Proceed with confidence."
        out = f"⚠️ {len(results)} matching anti-patterns!\n\n"
        for r in results:
            out += f"### 🚨 [{r['severity'].upper()}] {r['mistake']}\n- Root Cause: {r['root_cause']}\n- Fix: {r['fix']}\n\n"

        # Semantic Compression: Token bounding to prevent context window overflow
        MAX_CHARS = 6000
        if len(out) > MAX_CHARS:
            out = (
                out[:MAX_CHARS]
                + "\n\n...[TRUNCATED FOR CONTEXT WINDOW BUDGET: Refine your approach description to see more specific anti-patterns]..."
            )
        return out

    @mcp.tool()
    def resolve_prospective_failure(node_id: str, occurred: bool, evidence: str = "") -> str:
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

                    props = node["properties"]
                    props["evidence"] = evidence
                    props["evaluated_at"] = datetime.utcnow().isoformat()
                    conn = store.graph._get_conn()
                    try:
                        conn.execute("UPDATE graph_nodes SET properties = ? WHERE id = ?", (json.dumps(props), node_id))
                    finally:
                        store.graph._close(conn)
            status = "OCCURRED ⚠️" if occurred else "PREVENTED ✅"
            return f"{status} Prospective failure {node_id} resolved."
        except Exception as e:
            return f"❌ Failed to resolve: {str(e)}"

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

        configured_url = os.environ.get("ELITE_SYNC_URL") or os.environ.get("TEAM_SYNC_URL") or remote_url
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
            except (OSError, ValueError, TypeError) as exc:
                # Ignore corrupt or missing cursor and start from baseline
                _ = str(exc)

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
                except OSError as exc:
                    # Non-critical: OS temporary cleanup will reclaim orphaned temp file
                    _ = str(exc)
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
