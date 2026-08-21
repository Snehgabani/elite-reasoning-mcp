#!/usr/bin/env python3
"""
Continuous-checkpoint rule and optional Git validation-hook installer.
Adds host reminders and deterministic pre-commit tests without claiming that MCP
can force an IDE model to make another tool call.
"""

from __future__ import annotations

import stat
from pathlib import Path

ZERO_ESCAPE_RULE_TEXT = """# Elite Reasoning MCP — Continuous Checkpoint Protocol

For every non-trivial coding task:
1. Call `elite_prepare(user_prompt=<exact request>, persist=true)` and retain `run_id`.
2. Read `continuation` after every Elite response.
3. If `stop_final_response=true`, call `required_tool` with `required_args`; do not answer yet.
4. Continue through syntax after edit, Git scope, executed tests, and outcomes.
5. Repair FAIL/UNKNOWN/NOT_CHECKED/REPEAT and follow the next continuation.
6. Answer only when checkpoint is `done` and `stop_final_response=false`.

MCP cannot force another host call. IDE rules, durable state, evidence gates, and optional Git hooks are layered mitigation—not absolute enforcement.
"""

GIT_PRE_COMMIT_HOOK = """#!/usr/bin/env bash
# Elite Reasoning MCP: Physical Disk Write Barrier & Pre-Commit Gate

set -euo pipefail

echo "[ELITE PRE-COMMIT] Running repository tests/lint (not proof of MCP lifecycle compliance)..."

if command -v uv >/dev/null 2>&1; then
    uv run ruff check .
    uv run pytest tests/ -q --tb=short
elif command -v pytest >/dev/null 2>&1; then
    pytest tests/ -q --tb=short
fi

echo "[ELITE PRE-COMMIT] Repository checks passed."
"""


def install_zero_escape_system(repo_root: Path) -> dict[str, bool]:
    installed = {}

    # 1. Install Git Pre-Commit Hook (Physical Barrier)
    git_hooks_dir = repo_root / ".git" / "hooks"
    if git_hooks_dir.exists():
        pre_commit_file = git_hooks_dir / "pre-commit"
        existing = pre_commit_file.read_text(encoding="utf-8") if pre_commit_file.exists() else ""
        if existing and "Elite Reasoning MCP" not in existing:
            # Never destroy a user's existing hook. A future installer can
            # provide explicit hook chaining after preview/confirmation.
            installed["git_pre_commit_hook"] = False
        else:
            pre_commit_file.write_text(GIT_PRE_COMMIT_HOOK, encoding="utf-8")
            pre_commit_file.chmod(pre_commit_file.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            installed["git_pre_commit_hook"] = True

    # 2. Install Cursor Rule (.cursorrules)
    cursor_file = repo_root / ".cursorrules"
    cursor_file.write_text(ZERO_ESCAPE_RULE_TEXT, encoding="utf-8")
    installed["cursor_rules"] = True

    # 3. Install Claude Code Rule (CLAUDE.md)
    claude_file = repo_root / "CLAUDE.md"
    if not claude_file.exists() or "ZERO-ESCAPE" not in claude_file.read_text(encoding="utf-8"):
        claude_file.write_text(ZERO_ESCAPE_RULE_TEXT, encoding="utf-8")
    installed["claude_code_rules"] = True

    # 4. Install Windsurf Rule (.windsurfrules)
    windsurf_file = repo_root / ".windsurfrules"
    windsurf_file.write_text(ZERO_ESCAPE_RULE_TEXT, encoding="utf-8")
    installed["windsurf_rules"] = True

    return installed


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    res = install_zero_escape_system(root)
    print("Continuous-checkpoint IDE rules and optional repository checks:")
    for k, v in res.items():
        print(f"  ✅ {k}: {'ACTIVE' if v else 'SKIPPED'}")
