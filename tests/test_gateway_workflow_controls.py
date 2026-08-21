import os
import subprocess
import sys
from pathlib import Path

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
    assert prepared.goal
    assert prepared.constraints
    assert prepared.next_action in {"none", "evidence", "verify_constraints", "verify_tests"}


@pytest.mark.asyncio
async def test_gateway_constraint_and_syntax_verification(tmp_path):
    mcp = create_mcp_server(str(tmp_path / "brain"))
    tools = mcp._tool_manager._tools

    code = "def add(a, b):\n    return a + b\n"
    syntax = await tools["elite_verify"].fn(check="syntax", code=code)
    assert syntax.data["passed"] is True
    assert syntax.verification_status.value == "PASS"
    assert syntax.subject_digest.startswith("sha256:")
    assert syntax.data["subject_digest"] == syntax.subject_digest
    assert syntax.data["evidence_ids"] == [syntax.evidence[0].id]
    assert syntax.evidence[0].subject_digest == syntax.subject_digest

    repeated = await tools["elite_verify"].fn(check="syntax", code=code)
    changed = await tools["elite_verify"].fn(check="syntax", code=code + "\n# changed")
    assert repeated.evidence[0].id == syntax.evidence[0].id
    assert changed.subject_digest != syntax.subject_digest

    constraints = await tools["elite_verify"].fn(
        check="constraints",
        query="Reply in JSON. At most 20 words. Do not mention tools.",
        draft='{"ok": true, "reason": "done"}',
    )
    assert "pass_rate" in constraints.data
    assert constraints.data["pass_rate"] >= 0.5

    prepared = await tools["elite_prepare"].fn(
        user_prompt="Reply in JSON. At most 20 words. Do not mention tools.",
        persist=True,
    )
    assert prepared.playbook
    assert prepared.expected_outcomes
    assert prepared.allowed_tools
    assert "elite_verify" in prepared.allowed_tools
    assert prepared.repeat_until

    outcomes = await tools["elite_verify"].fn(
        check="outcomes",
        run_id=prepared.run_id,
        draft='{"ok": true, "reason": "done"}',
    )
    assert outcomes.data["action"] in {"DONE", "REPEAT"}
    assert "passed" in outcomes.data
    assert outcomes.verification_status.value in {"PASS", "FAIL"}
    assert outcomes.schema_version == "1.1"

    not_executed = await tools["elite_verify"].fn(check="tests", command="pytest -q")
    assert not_executed.verification_status.value == "NOT_CHECKED"
    assert not_executed.data["executed"] is False
    assert not_executed.data["verification_status"] == "NOT_CHECKED"


@pytest.mark.asyncio
async def test_gateway_verifies_git_scope_and_binds_repository_snapshot(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "tests@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Elite Tests"], check=True)
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
    (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
    monkeypatch.setenv("ELITE_PROJECT_ROOTS", str(repo))

    mcp = create_mcp_server(str(tmp_path / "brain"))
    verify = mcp._tool_manager._tools["elite_verify"].fn
    passed = await verify(check="diff", project_root=str(repo), allowed_files=["app.py"])
    assert passed.verification_status.value == "PASS"
    assert passed.data["changed_files"][0]["path"] == "app.py"
    assert passed.subject_digest == passed.evidence[0].subject_digest

    (repo / "extra.py").write_text("outside = True\n", encoding="utf-8")
    failed = await verify(check="diff", project_root=str(repo), allowed_files=["app.py"])
    assert failed.verification_status.value == "FAIL"
    assert failed.data["out_of_scope"] == ["extra.py"]
    assert failed.subject_digest != passed.subject_digest


@pytest.mark.asyncio
async def test_outcomes_require_fresh_persisted_test_and_repository_evidence(tmp_path, monkeypatch):
    repo = tmp_path / "tested-repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "tests@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Elite Tests"], check=True)
    (repo / ".gitignore").write_text(".pytest_cache/\n__pycache__/\n", encoding="utf-8")
    (repo / "app.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    (repo / "test_app.py").write_text("from app import value\n\ndef test_value():\n    assert value() == 2\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
    (repo / "app.py").write_text("def value():\n    return 2\n", encoding="utf-8")

    monkeypatch.setenv("ELITE_PROJECT_ROOTS", str(repo))
    monkeypatch.setenv("ELITE_ALLOW_TEST_COMMAND", "1")
    monkeypatch.setenv("PATH", str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""))
    mcp = create_mcp_server(str(tmp_path / "evidence-brain"))
    verify = mcp._tool_manager._tools["elite_verify"].fn
    prepared = await mcp._tool_manager._tools["elite_prepare"].fn(
        user_prompt="Fix code only app.py. Must run pytest.", persist=True
    )
    draft = "Updated app.py and ran pytest; 1 test passed."

    missing = await verify(
        check="outcomes", run_id=prepared.run_id, draft=draft, project_root=str(repo)
    )
    assert missing.data["action"] == "REPEAT"
    assert any("no independently executed" in item for item in missing.data["unmet"])
    assert any("syntax" in item for item in missing.data["unmet"])

    syntax = await verify(
        check="syntax",
        run_id=prepared.run_id,
        code=(repo / "app.py").read_text(encoding="utf-8"),
        project_root=str(repo),
    )
    assert syntax.verification_status.value == "PASS"
    assert syntax.continuation["checkpoint"] == "verify_repository_scope"

    diff = await verify(check="diff", run_id=prepared.run_id, project_root=str(repo))
    assert diff.verification_status.value == "PASS"
    assert diff.continuation["checkpoint"] == "run_tests"

    tests = await verify(
        check="tests",
        run_id=prepared.run_id,
        command="pytest -q",
        project_root=str(repo),
    )
    assert tests.verification_status.value == "PASS"
    assert tests.data["repository_snapshot_digest"].startswith("sha256:")
    assert tests.continuation["checkpoint"] == "verify_outcomes"
    stored = mcp._elite_store.list_workflow_evidence(prepared.run_id, "tests")
    assert stored[0]["id"] == tests.evidence[0].id

    second_run = await mcp._tool_manager._tools["elite_prepare"].fn(
        user_prompt="Fix code only app.py. Must run pytest.", persist=True
    )
    replay_attempt = await verify(
        check="outcomes", run_id=second_run.run_id, draft=draft, project_root=str(repo)
    )
    assert replay_attempt.data["action"] == "REPEAT"
    assert replay_attempt.data["evidence_gate"]["accepted_evidence_ids"] == []

    complete = await verify(
        check="outcomes", run_id=prepared.run_id, draft=draft, project_root=str(repo)
    )
    assert complete.data["action"] == "DONE"
    assert complete.data["evidence_gate"]["accepted_evidence_ids"] == [tests.evidence[0].id]
    assert complete.continuation["checkpoint"] == "done"
    assert complete.continuation["stop_final_response"] is False

    (repo / "app.py").write_text("def value():\n    return 3\n", encoding="utf-8")
    stale = await verify(
        check="outcomes", run_id=prepared.run_id, draft=draft, project_root=str(repo)
    )
    assert stale.data["action"] == "REPEAT"
    assert any("changed after" in item for item in stale.data["unmet"])


@pytest.mark.asyncio
async def test_gateway_exposes_privacy_safe_local_monitoring(tmp_path):
    mcp = create_mcp_server(str(tmp_path / "brain"))
    tools = mcp._tool_manager._tools

    prepared = await tools["elite_prepare"].fn(user_prompt="Build a monitored feature.", persist=True)
    monitoring = await tools["elite_admin"].fn(action="monitoring")

    assert monitoring.data["local_only"] is True
    summary = monitoring.data["operational_summary"]
    assert summary["tool_invocations"] >= 1
    assert "workflow_statuses" in summary
    assert "memory_items" in summary
    assert summary["continuity"]["prepare_only_runs"] == 1
    assert summary["continuity"]["post_prepare_continuation_rate"] == 0.0

    await tools["elite_verify"].fn(
        check="syntax", run_id=prepared.run_id, code="def monitored() -> bool:\n    return True\n"
    )
    continued = await tools["elite_admin"].fn(action="monitoring")
    assert continued.data["operational_summary"]["continuity"]["runs_with_mid_work_checks"] == 1
    assert continued.data["operational_summary"]["continuity"]["post_prepare_continuation_rate"] == 1.0


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
