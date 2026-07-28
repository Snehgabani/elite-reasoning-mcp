import pytest

from core.integration.mcp_server import create_mcp_server
from core.tools.errors import EliteToolError


@pytest.mark.asyncio
async def test_gateway_emits_phase_prevention_guidance_in_its_typed_contract(tmp_path):
    mcp = create_mcp_server(str(tmp_path / "brain"))

    result = await mcp._tool_manager._tools["elite_prepare"].fn(
        user_prompt="Design an architecture for a release-ready API.",
        persist=True,
    )

    warnings = "\n".join(result.warnings)
    assert "architecture_checklist" in warnings
    assert "gap_analysis_before_present" in warnings


@pytest.mark.asyncio
async def test_gateway_requires_evidence_and_ordered_workflow_completion(tmp_path):
    mcp = create_mcp_server(str(tmp_path / "brain"))
    tools = mcp._tool_manager._tools
    prepared = await tools["elite_prepare"].fn(user_prompt="Build a tested feature.", persist=True)

    with pytest.raises(EliteToolError, match="Terminal workflow updates require"):
        await tools["elite_progress"].fn(
            run_id=prepared.run_id,
            action="update",
            step_index=1,
            step_status="passed",
        )

    with pytest.raises(EliteToolError, match="earlier workflow steps"):
        await tools["elite_progress"].fn(
            run_id=prepared.run_id,
            action="update",
            step_index=2,
            step_status="passed",
            evidence="plan complete",
        )

    for step_index in range(1, 7):
        progress = await tools["elite_progress"].fn(
            run_id=prepared.run_id,
            action="update",
            step_index=step_index,
            step_status="passed",
            evidence=f"evidence for step {step_index}",
        )

    assert progress.workflow_status == "completed"
    assert all(step.status == "passed" for step in progress.steps)


@pytest.mark.asyncio
async def test_gateway_exposes_privacy_safe_local_monitoring(tmp_path):
    mcp = create_mcp_server(str(tmp_path / "brain"))
    tools = mcp._tool_manager._tools

    await tools["elite_prepare"].fn(user_prompt="Build a monitored feature.", persist=True)
    monitoring = await tools["elite_admin"].fn(action="monitoring")

    assert monitoring.data["local_only"] is True
    summary = monitoring.data["operational_summary"]
    assert summary["tool_invocations"] >= 1
    assert "workflow_statuses" in summary
    assert "memory_items" in summary


@pytest.mark.asyncio
async def test_gateway_memory_can_be_forgotten_and_ephemeral_runs_are_labeled(tmp_path):
    mcp = create_mcp_server(str(tmp_path / "brain"))
    tools = mcp._tool_manager._tools

    ephemeral = await tools["elite_prepare"].fn(
        user_prompt="Draft a short task without a durable run.",
        persist=False,
    )
    assert ephemeral.persisted is False
    assert "not durable" in " ".join(ephemeral.warnings)

    remembered = await tools["elite_memory"].fn(
        action="remember",
        content="The release check uses pytest and ruff.",
        memory_type="project_fact",
        scope="test",
    )
    assert remembered.memory_id is not None

    assert tools["elite_memory"].annotations.destructiveHint is True
    with pytest.raises(EliteToolError, match="confirm=true"):
        await tools["elite_memory"].fn(action="forget", memory_id=remembered.memory_id)

    forgotten = await tools["elite_memory"].fn(action="forget", memory_id=remembered.memory_id, confirm=True)
    assert forgotten.deleted is True
    assert mcp._elite_store.get_memory_item(remembered.memory_id, include_quarantined=True) is None


@pytest.mark.asyncio
async def test_gateway_middleware_merges_tool_and_prevention_warnings(tmp_path):
    mcp = create_mcp_server(str(tmp_path / "brain"))
    tools = mcp._tool_manager._tools

    result = await tools["elite_prepare"].fn(
        user_prompt="Build a tested feature without a durable run.",
        persist=False,
    )

    warnings = "\n".join(result.warnings)
    assert "not durable" in warnings
    assert "verify_before_commit" in warnings
