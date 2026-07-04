"""Run release gates for elite-reasoning-mcp.

This intentionally separates always-on release gates from the broader typing
debt audit. Full-repo pyright is still useful, but the current release gate
requires the new workflow/doctor/eval slice to be type-clean.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FOCUSED_PYRIGHT = [
    "core/tools/doctor.py",
    "core/tools/workflow.py",
    "core/orchestration/workflow_run.py",
    "core/eval/exporters.py",
    "tests/test_workflow_release.py",
]


def run_step(name: str, command: list[str]) -> None:
    print(f"\n==> {name}")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    run_step("pytest", ["uv", "run", "--extra", "dev", "pytest"])
    run_step("ruff", ["uv", "run", "--extra", "dev", "ruff", "check", "core", "tests"])
    run_step("focused pyright", ["uv", "run", "--extra", "dev", "pyright", *FOCUSED_PYRIGHT])
    run_step("build", ["uv", "build"])
    run_step(
        "mcp smoke",
        [
            "uv",
            "run",
            "--extra",
            "dev",
            "python",
            "-c",
            (
                "from core.integration.mcp_server import create_mcp_server; "
                "mcp=create_mcp_server('/tmp/elite-release-check-brain'); "
                "tools=set(mcp._tool_manager._tools); "
                "required={'elite_doctor','workflow_run','export_eval_harness','memory_context_pack'}; "
                "missing=required-tools; "
                "assert not missing, missing; "
                "print(f'tool_count={len(tools)} release_tools=ok')"
            ),
        ],
    )
    print("\nRelease gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
