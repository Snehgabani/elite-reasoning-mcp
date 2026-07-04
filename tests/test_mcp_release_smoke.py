import pytest

from core.integration.mcp_server import create_mcp_server


def test_mcp_server_exposes_release_grade_tools(tmp_path):
    mcp = create_mcp_server(str(tmp_path / "brain"))
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


@pytest.mark.asyncio
async def test_release_grade_tools_run_through_middleware(tmp_path):
    mcp = create_mcp_server(str(tmp_path / "brain"))
    tools = mcp._tool_manager._tools

    doctor = await tools["elite_doctor"].fn(output_format="markdown")
    workflow = await tools["workflow_run"].fn(
        user_prompt="Build a release-ready MCP with evidence and validation.",
        persist=True,
        output_format="markdown",
    )
    exported = await tools["export_eval_harness"].fn(harness="promptfoo")

    assert "# Elite MCP Doctor" in doctor
    assert "**Run ID:**" in workflow
    assert "promptfooconfig.yaml" in exported
