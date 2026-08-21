"""Restricted adapter for explicitly allowlisted local test commands."""

from __future__ import annotations

import os
import shlex
import subprocess
from typing import Any

ALLOWED_TEST_PREFIXES = (
    "pytest",
    "python -m pytest",
    "python3 -m pytest",
    "ruff",
    "python -m ruff",
    "python3 -m ruff",
)

_ENV_ALLOWLIST = frozenset({"HOME", "LANG", "LC_ALL", "PATH", "SYSTEMROOT", "TEMP", "TMP", "TMPDIR", "VIRTUAL_ENV"})


class CommandInputError(ValueError):
    """Raised when a command request is missing required input."""


def _restricted_environment() -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if key in _ENV_ALLOWLIST}
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def run_allowlisted_command(command: str, *, cwd: str = "", timeout_seconds: int = 30) -> dict[str, Any]:
    """Run pytest or Ruff directly as argv, never through a shell."""
    cleaned = (command or "").strip()
    if not cleaned:
        raise CommandInputError("command is required for check=tests.")
    lowered = cleaned.lower()
    if not any(lowered == prefix or lowered.startswith(prefix + " ") for prefix in ALLOWED_TEST_PREFIXES):
        return {
            "passed": False,
            "executed": False,
            "reason": "command is not on the pytest/ruff allowlist",
            "command": cleaned,
        }
    if os.environ.get("ELITE_ALLOW_TEST_COMMAND", "").strip() != "1":
        return {
            "passed": False,
            "executed": False,
            "reason": "set ELITE_ALLOW_TEST_COMMAND=1 to run allowlisted tests locally",
            "command": cleaned,
        }
    try:
        completed = subprocess.run(
            shlex.split(cleaned),
            capture_output=True,
            text=True,
            timeout=max(1, min(int(timeout_seconds), 120)),
            check=False,
            cwd=cwd or None,
            env=_restricted_environment(),
        )
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "executed": False,
            "reason": f"command timed out after {max(1, min(int(timeout_seconds), 120))} seconds",
            "command": cleaned,
        }
    except OSError as exc:
        return {
            "passed": False,
            "executed": False,
            "reason": f"command execution failed: {type(exc).__name__}",
            "command": cleaned,
        }
    output = ((completed.stdout or "") + (completed.stderr or ""))[-1500:]
    return {
        "passed": completed.returncode == 0,
        "executed": True,
        "returncode": completed.returncode,
        "output": output,
        "command": cleaned,
    }
