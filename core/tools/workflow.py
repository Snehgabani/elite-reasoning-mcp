"""Workflow and memory tools for release-grade agent execution."""

from __future__ import annotations

import json

from core.orchestration.workflow_run import build_workflow_run, workflow_run_markdown, workflow_status_markdown


def _json_block(data: object) -> str:
    return "```json\n" + json.dumps(data, indent=2, sort_keys=True) + "\n```"


def register(mcp, store):
    """Register workflow flight-recorder and memory quality-gate tools."""

    @mcp.tool()
    def workflow_run(user_prompt: str, persist: bool = True, output_format: str = "markdown") -> str:
        """Create an evidence-gated workflow run for a non-trivial task.

        Use this for build/debug/research/release tasks that need durable
        planning, validation gates, memory retrieval, confidence, and writeback.

        Args:
            user_prompt: The user request to execute.
            persist: Persist a run ID and planned steps to the local flight recorder.
            output_format: markdown or json.
        """
        run = build_workflow_run(user_prompt, store=store, persist=persist)
        if output_format.lower() == "json":
            return json.dumps(run, indent=2, sort_keys=True)
        return workflow_run_markdown(run)

    @mcp.tool()
    def workflow_status(run_id: str) -> str:
        """Return the stored status and step list for a workflow run."""
        return workflow_status_markdown(store.get_workflow_run(run_id))

    @mcp.tool()
    def workflow_update_step(run_id: str, step_index: int, status: str, evidence: str = "") -> str:
        """Update a workflow step with validation evidence.

        Args:
            run_id: Workflow run ID returned by workflow_run.
            step_index: 1-based step index.
            status: pending, running, passed, failed, skipped, or blocked.
            evidence: Short evidence note, command, source, or blocker.
        """
        allowed = {"pending", "running", "passed", "failed", "skipped", "blocked"}
        normalized = (status or "").strip().lower()
        if normalized not in allowed:
            return f"Invalid status `{status}`. Allowed: {', '.join(sorted(allowed))}"
        ok = store.update_workflow_step(run_id, step_index, normalized, evidence)
        if not ok:
            return f"Workflow `{run_id}` step {step_index} was not found."
        return f"Workflow `{run_id}` step {step_index} updated to `{normalized}`."

    @mcp.tool()
    def remember_context(
        memory_type: str,
        content: str,
        scope: str = "global",
        source: str = "manual",
        confidence: float = 0.7,
        trust_score: float = 0.7,
        privacy_class: str = "internal",
        expires_at: str = "",
        tags: str = "",
    ) -> str:
        """Record a scoped memory item with poisoning/privacy quality gates.

        Low-trust, low-confidence, or sensitive memories are quarantined from
        automatic context packs but retained for audit.
        """
        row_id = store.record_memory_item(
            memory_type=memory_type,
            content=content,
            scope=scope,
            source=source,
            confidence=confidence,
            trust_score=trust_score,
            privacy_class=privacy_class,
            expires_at=expires_at,
            tags=tags,
        )
        item = store.search_memory_items(content, include_quarantined=True, limit=1, min_trust=0.0)
        quarantined = item[0]["quarantined"] if item else False
        status = "quarantined" if quarantined else "trusted"
        return f"Memory item #{row_id} recorded as `{status}`."

    @mcp.tool()
    def memory_context_pack(query: str, scope: str = "", limit: int = 8, min_trust: float = 0.5) -> str:
        """Return trusted memory context for a task.

        Args:
            query: Task or topic to retrieve context for.
            scope: Optional project/user scope. Global memories are included.
            limit: Maximum memory items.
            min_trust: Minimum trust score for automatic injection.
        """
        items = store.search_memory_items(query=query, scope=scope, limit=limit, min_trust=min_trust)
        if not items:
            return "No trusted memory items matched this query."
        lines = ["# Trusted Memory Context", ""]
        for item in items:
            lines.append(
                f"- #{item['id']} `{item['memory_type']}` scope=`{item['scope']}` "
                f"confidence={item['confidence']:.2f} trust={item['trust_score']:.2f}: {item['content']}"
            )
        lines.extend(["", "## JSON", _json_block({"items": items})])
        return "\n".join(lines)
