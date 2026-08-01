import json
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from core.integration.mcp_server import _default_brain_dir, main
from core.runtime import package_version, runtime_identity

CORE_TOOLS = {
    "elite_prepare",
    "elite_progress",
    "elite_verify",
    "elite_memory",
    "elite_admin",
}


def test_runtime_identity_prefers_the_running_virtualenv_entrypoint(tmp_path, monkeypatch):
    entrypoint = tmp_path / "venv" / "bin" / "elite-reasoning-mcp"
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [str(entrypoint)])
    monkeypatch.setattr(sys, "executable", str(entrypoint.parent / "python"))

    assert runtime_identity()["entrypoint"] == str(entrypoint.resolve())


def test_brain_dir_expands_home_in_environment_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ELITE_BRAIN_DIR", "~/.elite-private/brain")

    assert _default_brain_dir() == str(tmp_path / ".elite-private" / "brain")


@pytest.mark.asyncio
async def test_stdio_protocol_advertises_runtime_version_and_typed_errors(tmp_path):
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "core.integration.mcp_server", "--brain-dir", str(tmp_path / "brain")],
    )

    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            tools = await session.list_tools()
            secret_run_id = "sk-12345678901234567890"
            invalid = await session.call_tool("elite_progress", {"run_id": secret_run_id})
            prepared = await session.call_tool(
                "elite_prepare",
                {"user_prompt": "Build a feature with tests and validation.", "persist": True},
            )

    assert initialized.serverInfo.version == package_version()
    assert {tool.name for tool in tools.tools} == CORE_TOOLS
    assert all(tool.annotations is not None and tool.annotations.title for tool in tools.tools)
    assert invalid.isError is True
    assert "validation_error" in invalid.content[0].text
    assert secret_run_id not in invalid.content[0].text
    assert "Traceback" not in invalid.content[0].text
    assert prepared.isError is not True
    assert prepared.structuredContent is not None
    assert prepared.structuredContent["status"] == "ok"


def test_cli_reports_version_doctor_and_safe_upgrade_preview(tmp_path, capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == package_version()

    assert main(["upgrade", "--dry-run"]) == 0
    assert "upgrade elite-reasoning-mcp" in capsys.readouterr().out

    assert main(["--brain-dir", str(tmp_path / "brain"), "doctor", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["tool_profile"] == "core"
    assert report["protocol_server_version"] == package_version()
    assert report["tool_count"] == 5
