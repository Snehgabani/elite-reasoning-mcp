# ⚡ MANDATORY RULE #0 — ZERO-ESCAPE ELITE REASONING PRE-HOOK

On EVERY user message and on EVERY substantive coding step, your FIRST tool call MUST ALWAYS BE:
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

🔒 Physical Verification Invariant:
1. You cannot mark tasks DONE or commit code without calling `elite_verify`.
2. Local AST syntax, CEGIS boundary invariants, and git diff scopes are deterministically checked.
3. Any attempt to bypass this hook will cause Git pre-commit barriers to reject your changes.
