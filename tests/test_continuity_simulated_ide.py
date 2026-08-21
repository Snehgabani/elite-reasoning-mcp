import os
import subprocess
import sys
from pathlib import Path

import pytest

from core.integration.mcp_server import create_mcp_server
from scripts.install_zero_escape_hooks import install_zero_escape_system


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "sim@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Simulated IDE"], check=True)
    (repo / ".gitignore").write_text(".pytest_cache/\n__pycache__/\n", encoding="utf-8")
    (repo / "app.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    (repo / "test_app.py").write_text("from app import value\n\ndef test_value():\n    assert value() == 2\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
    (repo / "app.py").write_text("def value():\n    return 2\n", encoding="utf-8")
    return repo


@pytest.fixture
def simulated_ide(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.setenv("ELITE_PROJECT_ROOTS", str(repo))
    monkeypatch.setenv("ELITE_ALLOW_TEST_COMMAND", "1")
    monkeypatch.setenv("PATH", str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""))
    server = create_mcp_server(str(tmp_path / "brain"))
    return repo, server._tool_manager._tools


@pytest.mark.asyncio
async def test_prepare_only_amnesiac_is_left_at_a_blocking_mid_work_checkpoint(simulated_ide):
    _, tools = simulated_ide
    prepared = await tools["elite_prepare"].fn(
        user_prompt="Fix code only app.py. Must run pytest.", persist=True
    )

    assert prepared.continuation["checkpoint"] == "verify_changed_code"
    assert prepared.continuation["required_tool"] == "elite_verify"
    assert prepared.continuation["stop_final_response"] is True


@pytest.mark.asyncio
async def test_agent_that_jumps_from_prepare_to_final_answer_is_rejected(simulated_ide):
    repo, tools = simulated_ide
    prepared = await tools["elite_prepare"].fn(
        user_prompt="Fix code only app.py. Must run pytest.", persist=True
    )
    shortcut = await tools["elite_verify"].fn(
        check="outcomes",
        run_id=prepared.run_id,
        draft="Updated app.py. All tests passed.",
        project_root=str(repo),
    )

    assert shortcut.data["action"] == "REPEAT"
    assert shortcut.verification_status.value == "FAIL"
    assert shortcut.continuation["checkpoint"] == "verify_changed_code"
    assert shortcut.continuation["stop_final_response"] is True


@pytest.mark.asyncio
async def test_context_dilution_does_not_erase_required_next_call(simulated_ide):
    _, tools = simulated_ide
    prepared = await tools["elite_prepare"].fn(
        user_prompt="Fix code only app.py. Must run pytest.", persist=True
    )

    # Twenty simulated host reasoning/file-navigation turns occur without Elite.
    # On re-entry, durable state still returns the exact missed checkpoint.
    for _ in range(20):
        status = await tools["elite_progress"].fn(run_id=prepared.run_id, action="status")
        assert status.continuation["checkpoint"] == "verify_changed_code"
        assert status.continuation["stop_final_response"] is True


@pytest.mark.asyncio
async def test_compliant_agent_is_chained_through_all_checkpoints(simulated_ide):
    repo, tools = simulated_ide
    verify = tools["elite_verify"].fn
    prepared = await tools["elite_prepare"].fn(
        user_prompt="Fix code only app.py. Must run pytest.", persist=True
    )
    run_id = prepared.run_id

    syntax = await verify(
        check="syntax",
        run_id=run_id,
        code=(repo / "app.py").read_text(encoding="utf-8"),
        project_root=str(repo),
    )
    assert syntax.continuation["checkpoint"] == "verify_repository_scope"

    diff = await verify(check="diff", run_id=run_id, project_root=str(repo))
    assert diff.continuation["checkpoint"] == "run_tests"

    tests = await verify(check="tests", run_id=run_id, command="pytest -q", project_root=str(repo))
    assert tests.verification_status.value == "PASS"
    assert tests.continuation["checkpoint"] == "verify_outcomes"

    outcomes = await verify(
        check="outcomes",
        run_id=run_id,
        draft="Updated app.py and executed pytest; 1 test passed.",
        project_root=str(repo),
    )
    assert outcomes.data["action"] == "DONE"
    assert outcomes.continuation["checkpoint"] == "done"
    assert outcomes.continuation["stop_final_response"] is False


@pytest.mark.asyncio
async def test_post_verification_edit_reopens_earliest_stale_checkpoint(simulated_ide):
    repo, tools = simulated_ide
    verify = tools["elite_verify"].fn
    prepared = await tools["elite_prepare"].fn(
        user_prompt="Fix code only app.py. Must run pytest.", persist=True
    )
    run_id = prepared.run_id
    await verify(
        check="syntax",
        run_id=run_id,
        code=(repo / "app.py").read_text(encoding="utf-8"),
        project_root=str(repo),
    )
    await verify(check="diff", run_id=run_id, project_root=str(repo))
    await verify(check="tests", run_id=run_id, command="pytest -q", project_root=str(repo))

    (repo / "app.py").write_text("def value():\n    return 3\n", encoding="utf-8")
    stale = await verify(
        check="outcomes",
        run_id=run_id,
        draft="Updated app.py and executed tests.",
        project_root=str(repo),
    )
    assert stale.data["action"] == "REPEAT"
    assert stale.continuation["checkpoint"] == "verify_changed_code"


def test_rule_installer_uses_real_core_tools_and_preserves_existing_git_hook(tmp_path):
    hooks = tmp_path / ".git/hooks"
    hooks.mkdir(parents=True)
    existing = hooks / "pre-commit"
    existing.write_text("#!/bin/sh\necho user-hook\n", encoding="utf-8")

    result = install_zero_escape_system(tmp_path)
    assert result["git_pre_commit_hook"] is False
    assert "user-hook" in existing.read_text(encoding="utf-8")
    for rule_path in (tmp_path / ".cursorrules", tmp_path / "CLAUDE.md", tmp_path / ".windsurfrules"):
        text = rule_path.read_text(encoding="utf-8")
        assert "elite_prepare" in text
        assert "continuation" in text
        assert "elite_reason" not in text
        assert "cannot force" in text


@pytest.mark.asyncio
async def test_non_code_task_does_not_force_irrelevant_mid_work_tools(tmp_path):
    server = create_mcp_server(str(tmp_path / "brain"))
    prepared = await server._tool_manager._tools["elite_prepare"].fn(
        user_prompt="Explain dependency injection in two paragraphs.", persist=True
    )
    assert prepared.continuation["checkpoint"] == "verify_outcomes"
