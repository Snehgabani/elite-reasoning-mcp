import json
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from core.integration.mcp_server import main
from core.memory.persistent_store import EliteStore
from core.runtime import package_version, runtime_identity

CORE_TOOLS = {
    "elite_prepare",
    "elite_verify",
    "elite_memory",
}


def test_runtime_identity_prefers_the_running_virtualenv_entrypoint(tmp_path, monkeypatch):
    entrypoint = tmp_path / "venv" / "bin" / "elite-reasoning-mcp"
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [str(entrypoint)])
    monkeypatch.setattr(sys, "executable", str(entrypoint.parent / "python"))

    assert runtime_identity()["entrypoint"] == str(entrypoint.resolve())


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
            prompts = await session.list_prompts()
            goal_prompt = await session.get_prompt("goal", {"objective": "Fix authentication with tests"})
            secret_run_id = "sk-12345678901234567890"
            invalid = await session.call_tool("elite_verify", {"check": "status", "run_id": secret_run_id})
            prepared = await session.call_tool(
                "elite_prepare",
                {"user_prompt": "Build a feature with tests and validation.", "persist": True},
            )

    assert initialized.serverInfo.version == package_version()
    assert initialized.instructions is not None
    assert "continuation" in initialized.instructions
    assert "checkpoint=done" in initialized.instructions
    assert {tool.name for tool in tools.tools} == CORE_TOOLS
    assert {prompt.name for prompt in prompts.prompts} == {"goal"}
    assert "Fix authentication with tests" in goal_prompt.messages[0].content.text
    assert "continuation" in goal_prompt.messages[0].content.text
    assert all(tool.annotations is not None and tool.annotations.title for tool in tools.tools)
    assert invalid.isError is True
    assert "validation_error" in invalid.content[0].text
    assert secret_run_id not in invalid.content[0].text
    assert "Traceback" not in invalid.content[0].text
    assert prepared.isError is not True
    assert prepared.structuredContent is not None
    assert prepared.structuredContent["status"] == "ok"


def test_cli_exports_redacted_typed_workflow_evidence(tmp_path, capsys):
    brain = tmp_path / "brain"
    store = EliteStore(str(brain))
    store.record_workflow_run(
        {"run_id": "wf_export", "user_prompt": "test", "intent": "build"},
        [],
    )
    assert store.record_workflow_evidence(
        "wf_export",
        "tests",
        {
            "id": "ev_export",
            "verification_status": "PASS",
            "subject_digest": "sha256:subject",
            "artifact_digest": "sha256:artifact",
            "producer": "test",
            "payload": {"executed": True},
            "limitations": [],
            "collected_at": "2026-08-22T00:00:00Z",
        },
    )

    assert main(["--brain-dir", str(brain), "export-evidence", "wf_export", "--json"]) == 0
    exported = json.loads(capsys.readouterr().out)
    assert exported["run_id"] == "wf_export"
    assert exported["evidence_count"] == 1
    assert exported["evidence"][0]["id"] == "ev_export"


def test_cli_reports_version_doctor_and_safe_upgrade_preview(tmp_path, capsys, monkeypatch):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == package_version()

    assert main(["upgrade", "--dry-run"]) == 0
    assert "upgrade elite-verify-mcp" in capsys.readouterr().out

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert main(["init", "--ide", "cursor"]) == 2
    assert "without --yes" in capsys.readouterr().err
    assert main(["init", "--ide", "cursor", "--dry-run"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["status"] == "preview"
    assert preview["config"]["mcpServers"]["elite-reasoning"]["args"] == []
    assert not (tmp_path / "home/.cursor/mcp.json").exists()

    assert main(["--brain-dir", str(tmp_path / "brain"), "demo", "--json"]) == 0
    demo = json.loads(capsys.readouterr().out)
    assert demo["status"] == "ok"
    assert demo["tool_count"] == 3
    assert demo["failing_draft"]["verification_status"] == "FAIL"
    assert demo["passing_draft"]["verification_status"] == "PASS"
    assert demo["privacy"] == {"network_requests": 0, "raw_prompt_persisted": False}

    assert main(["--brain-dir", str(tmp_path / "brain"), "doctor", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["tool_profile"] == "core"
    assert report["protocol_server_version"] == package_version()
    assert report["tool_count"] == 3
    assert report["database_schema_version"] == report["expected_database_schema_version"] == 7
