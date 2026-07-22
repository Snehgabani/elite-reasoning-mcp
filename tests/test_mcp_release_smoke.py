import pytest

from core.integration.mcp_server import create_mcp_server
from core.tools.errors import EliteToolError

CORE_TOOLS = {
    "elite_prepare",
    "elite_progress",
    "elite_verify",
    "elite_memory",
    "elite_admin",
}


def test_default_server_exposes_a_compact_typed_surface(tmp_path):
    mcp = create_mcp_server(str(tmp_path / "brain"))
    tools = mcp._tool_manager._tools

    assert set(tools) == CORE_TOOLS
    assert not mcp._resource_manager._resources
    for tool in tools.values():
        assert tool.annotations is not None
        assert tool.annotations.title
        assert tool.output_schema["type"] == "object"
        assert "status" in tool.output_schema["properties"]

    memory_schema = tools["elite_memory"].parameters
    assert memory_schema["properties"]["action"]["enum"] == [
        "search",
        "remember",
        "approve",
        "forget",
    ]
    assert memory_schema["properties"]["content"]["maxLength"] == 5000
    assert memory_schema["properties"]["trust_score"]["minimum"] == 0.0
    assert memory_schema["properties"]["trust_score"]["maximum"] == 1.0


@pytest.mark.asyncio
async def test_core_tools_run_through_middleware_with_structured_results(tmp_path):
    mcp = create_mcp_server(str(tmp_path / "brain"))
    tools = mcp._tool_manager._tools

    verification = await tools["elite_verify"].fn(check="doctor")
    prepared = await tools["elite_prepare"].fn(
        user_prompt="Build a release-ready MCP with evidence and validation.",
        persist=True,
    )

    assert verification.status == "ok"
    assert verification.data["tool_count"] == 5
    assert prepared.status == "ok"
    assert prepared.run_id
    assert prepared.steps

    with pytest.raises(EliteToolError, match="validation_error"):
        await tools["elite_progress"].fn(run_id="missing")


def test_legacy_profile_retains_explicit_compatibility_surface(tmp_path):
    mcp = create_mcp_server(str(tmp_path / "brain"), tool_profile="legacy")
    tools = set(mcp._tool_manager._tools)

    assert len(tools) >= 90
    assert {
        "elite_doctor",
        "elite_doctor_json",
        "workflow_run",
        "workflow_status",
        "workflow_update_step",
        "remember_context",
        "memory_context_pack",
        "export_eval_harness",
    }.issubset(tools)
