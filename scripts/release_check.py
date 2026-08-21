"""Run release gates for elite-reasoning-mcp.

This intentionally separates always-on release gates from the broader legacy
typing-debt audit. The v2 runtime, privacy, tool contract, and middleware
slice must remain type-clean and is exercised through a real stdio MCP test.
"""

from __future__ import annotations

import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_SDIST_PARTS = frozenset(
    {
        ".next",
        ".venv",
        "_archive",
        "__pycache__",
        "brain",
        "brain_central",
        "build",
        "diagnostics",
        "dist",
        "node_modules",
        "telemetry-ui",
    }
)
FORBIDDEN_SDIST_NAMES = frozenset({"config.json", "team-memory.json"})
FORBIDDEN_SDIST_SUFFIXES = frozenset({".db", ".key", ".p12", ".pfx", ".pem", ".sqlite", ".sqlite3"})

FOCUSED_PYRIGHT = [
    "core/runtime.py",
    "core/privacy.py",
    "core/sync_security.py",
    "core/identity/user_profile.py",
    "core/integration/sync_server.py",
    "core/orchestration/workflow_run.py",
    "core/reasoning/task_contract.py",
    "core/reasoning/constraint_check.py",
    "core/reasoning/playbook.py",
    "core/evidence/grounded_search.py",
    "core/eval/blind_protocol.py",
    "core/tools/errors.py",
    "core/tools/error_boundary.py",
    "core/tools/gateway.py",
    "core/tools/doctor.py",
    "core/tools/orchestration.py",
    "core/middleware/chain.py",
    "core/middleware/fallback.py",
    "core/middleware/prevention.py",
    "core/middleware/telemetry.py",
]


def run_step(name: str, command: list[str]) -> None:
    print(f"\n==> {name}")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def verify_sdist_contents(archive_path: Path) -> None:
    """Reject local state, generated artifacts, and credentials in an sdist."""
    violations: list[str] = []
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
    except (OSError, tarfile.TarError) as exc:
        raise SystemExit(f"Could not inspect source distribution {archive_path.name}: {exc}") from exc

    for member in members:
        path = PurePosixPath(member.name)
        parts = tuple(part.lower() for part in path.parts if part not in {".", "/"})
        if not parts:
            continue

        name = path.name.lower()
        has_forbidden_part = any(part in FORBIDDEN_SDIST_PARTS or part == ".." for part in parts)
        has_forbidden_name = name in FORBIDDEN_SDIST_NAMES
        has_forbidden_suffix = path.suffix.lower() in FORBIDDEN_SDIST_SUFFIXES
        is_environment_file = name == ".env" or name.startswith(".env.")
        if has_forbidden_part or has_forbidden_name or has_forbidden_suffix or is_environment_file:
            violations.append(member.name)

    if violations:
        preview = ", ".join(sorted(violations)[:10])
        more = "" if len(violations) <= 10 else f" (+{len(violations) - 10} more)"
        raise SystemExit(f"Source distribution contains forbidden local or generated paths: {preview}{more}")


def main() -> int:
    run_step("lock integrity", ["uv", "lock", "--check"])
    run_step("public claims integrity", [sys.executable, "scripts/validate_claims.py"])
    run_step("pytest", ["uv", "run", "--extra", "dev", "pytest"])
    run_step("internal fixture pilot", ["uv", "run", "--extra", "dev", "python", "scripts/double_blind_eval.py"])
    run_step("ruff", ["uv", "run", "--extra", "dev", "ruff", "check", "core", "tests", "scripts"])
    run_step(
        "focused pyright",
        ["uv", "run", "--extra", "dev", "pyright", "--pythonpath", sys.executable, *FOCUSED_PYRIGHT],
    )
    run_step("high-severity security scan", ["uv", "run", "--extra", "dev", "bandit", "-q", "-r", "core", "-lll"])
    run_step("build", ["uv", "build", "--clear"])
    sdists = sorted((ROOT / "dist").glob("*.tar.gz"), key=lambda path: path.stat().st_mtime)
    if not sdists:
        raise SystemExit("Build completed without a source distribution artifact.")
    verify_sdist_contents(sdists[-1])
    print(f"Source distribution contents verified: {sdists[-1].name}")
    wheels = sorted((ROOT / "dist").glob("*.whl"), key=lambda path: path.stat().st_mtime)
    if not wheels:
        raise SystemExit("Build completed without a wheel artifact.")
    run_step(
        "wheel CLI smoke",
        [
            "uv",
            "run",
            "--isolated",
            "--no-project",
            "--with",
            str(wheels[-1]),
            "elite-reasoning-mcp",
            "--version",
        ],
    )
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
                "from core.runtime import package_version; "
                "mcp=create_mcp_server('/tmp/elite-release-check-brain'); "
                "tools=set(mcp._tool_manager._tools); "
                "required={'elite_prepare','elite_progress','elite_verify','elite_memory','elite_admin'}; "
                "assert tools == required, tools; "
                "assert mcp._mcp_server.version == package_version(); "
                "assert not mcp._resource_manager._resources; "
                "print(f'tool_count={len(tools)} core_protocol_identity=ok')"
            ),
        ],
    )
    print("\nRelease gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
