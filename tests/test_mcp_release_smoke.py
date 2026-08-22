import json
import subprocess
import sys

import pytest

from core.integration.mcp_server import create_mcp_server
from core.tools.errors import EliteToolError

CORE_TOOLS = {
    "elite_prepare",
    "elite_verify",
    "elite_memory",
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
        "associative",
    ]
    assert memory_schema["properties"]["content"]["maxLength"] == 5000


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
    assert verification.data["tool_count"] == 3
    assert prepared.status == "ok"
    assert prepared.run_id
    assert prepared.steps

    # elite_progress is now elite_verify(check="status")
    with pytest.raises(EliteToolError, match="validation_error"):
        await tools["elite_verify"].fn(check="status", run_id="missing")


def test_default_startup_does_not_import_legacy_cognitive_runtime(tmp_path):
    script = """
import json
import sys
from core.integration.mcp_server import create_mcp_server
server = create_mcp_server(sys.argv[1], tool_profile="core")
forbidden_prefixes = (
    "core.cognitive",
    "core.tools.cognitive_tools",
    "core.tools.reasoning_amplifier",
    "core.tools.verb_tools",
    "core.tools.goal_prompt_polisher",
    "core.tools.planning",
    "core.tools.orchestration",
    "core.integration.memory_bridge",
)
forbidden = sorted(name for name in sys.modules if name.startswith(forbidden_prefixes))
print(json.dumps({"tools": sorted(server._tool_manager._tools), "forbidden": forbidden}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "isolated-brain")],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    assert set(payload["tools"]) == CORE_TOOLS
    assert payload["forbidden"] == []
