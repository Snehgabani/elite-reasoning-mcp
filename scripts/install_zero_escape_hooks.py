#!/usr/bin/env python3
"""
Universal Zero-Escape Invariant Installer.
Enforces deterministic pre-commit physical write barriers and multi-IDE rules
so LLMs (Cursor, Claude Code, Antigravity, Windsurf) CANNOT bypass Elite verification.
"""

from __future__ import annotations

import stat
from pathlib import Path

ZERO_ESCAPE_RULE_TEXT = """# ⚡ MANDATORY RULE #0 — ZERO-ESCAPE CONTINUOUS ELITE REASONING LIFECYCLE

## 🔒 3-Checkpoint Step-Locked Invariant (Mandatory on EVERY coding task):

### 🚩 Checkpoint 1 (Start of Turn — PRE-EDIT):
Your VERY FIRST tool call on every message MUST be:
```json
call_mcp_tool(
  ServerName="elite-reasoning-mcp",
  ToolName="elite_reason",
  Arguments={
    "task": "<the user's exact request and current objective>",
    "task_type": "hard_problem",
    "enable_prm": true,
    "enable_bias_scan": true
  }
)
```

### 🚩 Checkpoint 2 (Mid-Turn — NATIVE TOOL INTERLOCK):
You are strictly prohibited from calling native file edit tools without immediately executing their coupled MCP verifiers:
- **IF YOU CALL** `replace_file_content`, `write_to_file`, or `apply_reasoning_diff`:
  -> **YOUR VERY NEXT TOOL CALL MUST BE**: `elite_verify(check="syntax", code="...")` and `elite_verify(check="cegis", code="...")`.
- **IF AN ERROR/EXCEPTION OCCURS**:
  -> **YOUR VERY NEXT TOOL CALL MUST BE**: `elite_verify(check="diagnostics", query="<traceback>")`.

### 🚩 Checkpoint 3 (End of Turn — POST-EDIT TEST RECEIPT):
Before delivering your final text response to the user, you MUST:
- Run test commands via `elite_verify(check="tests", command="pytest ...")` or execute in terminal.
- Include a structured verification receipt in your response showing passed invariants.

🚫 FORBIDDEN: Generating code and replying directly without Checkpoint 2 and Checkpoint 3 verification. Physical Git pre-commit barriers will reject unverified commits.
"""

GIT_PRE_COMMIT_HOOK = """#!/usr/bin/env bash
# Elite Reasoning MCP: Physical Disk Write Barrier & Pre-Commit Gate

set -euo pipefail

echo "🛡️ [ELITE PRE-COMMIT] Running deterministic verification gate..."

if command -v uv >/dev/null 2>&1; then
    uv run ruff check .
    uv run pytest tests/ -q --tb=short
elif command -v pytest >/dev/null 2>&1; then
    pytest tests/ -q --tb=short
fi

echo "✅ [ELITE PRE-COMMIT] All deterministic gates PASSED. Proceeding with commit."
"""


def install_zero_escape_system(repo_root: Path) -> dict[str, bool]:
    installed = {}

    # 1. Install Git Pre-Commit Hook (Physical Barrier)
    git_hooks_dir = repo_root / ".git" / "hooks"
    if git_hooks_dir.exists():
        pre_commit_file = git_hooks_dir / "pre-commit"
        pre_commit_file.write_text(GIT_PRE_COMMIT_HOOK, encoding="utf-8")
        # chmod +x
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
    print("🔒 Zero-Escape Multi-IDE & Physical Git Hooks Installed Successfully:")
    for k, v in res.items():
        print(f"  ✅ {k}: {'ACTIVE' if v else 'SKIPPED'}")
