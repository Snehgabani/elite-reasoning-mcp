import subprocess

import pytest

from core.verification.command import CommandInputError, run_allowlisted_command


def test_command_adapter_rejects_missing_and_non_allowlisted_commands(monkeypatch):
    with pytest.raises(CommandInputError, match="command is required"):
        run_allowlisted_command("")

    called = False

    def _unexpected(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr(subprocess, "run", _unexpected)
    result = run_allowlisted_command("rm -rf /tmp/example")
    assert result["executed"] is False
    assert "allowlist" in result["reason"]
    assert called is False


def test_command_adapter_uses_argv_restricted_environment_and_cwd(monkeypatch, tmp_path):
    captured = {}

    def _run(argv, **kwargs):
        captured["argv"] = argv
        captured.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout="1 passed\n", stderr="")

    monkeypatch.setenv("ELITE_ALLOW_TEST_COMMAND", "1")
    monkeypatch.setenv("SECRET_SHOULD_NOT_LEAK", "top-secret")
    monkeypatch.setattr(subprocess, "run", _run)

    result = run_allowlisted_command("pytest -q", cwd=str(tmp_path))
    assert result["passed"] is True
    assert captured["argv"] == ["pytest", "-q"]
    assert captured["cwd"] == str(tmp_path)
    assert captured["check"] is False
    assert "shell" not in captured
    assert "SECRET_SHOULD_NOT_LEAK" not in captured["env"]
    assert captured["env"]["PYTHONNOUSERSITE"] == "1"


def test_command_adapter_reports_timeout_without_exception_leak(monkeypatch):
    def _timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["pytest"], timeout=3)

    monkeypatch.setenv("ELITE_ALLOW_TEST_COMMAND", "1")
    monkeypatch.setattr(subprocess, "run", _timeout)
    result = run_allowlisted_command("pytest", timeout_seconds=3)
    assert result["executed"] is False
    assert result["reason"] == "command timed out after 3 seconds"


def test_command_adapter_accepts_polyglot_test_runners(monkeypatch, tmp_path):
    executed_cmds = []

    def _run(argv, **kwargs):
        executed_cmds.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="All checks passed\n", stderr="")

    monkeypatch.setenv("ELITE_ALLOW_TEST_COMMAND", "1")
    monkeypatch.setattr(subprocess, "run", _run)

    polyglot_commands = [
        "npm test",
        "npx vitest run",
        "tsc --noEmit",
        "cargo test --all",
        "cargo check",
        "go test ./...",
        "go vet ./...",
        "pyright core",
    ]

    for cmd in polyglot_commands:
        res = run_allowlisted_command(cmd, cwd=str(tmp_path))
        assert res["passed"] is True, f"Failed on command: {cmd}"
        assert res["executed"] is True

    assert len(executed_cmds) == len(polyglot_commands)
