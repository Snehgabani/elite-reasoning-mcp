---
name: 🐛 Bug Report
about: Something isn't working as expected
title: "[Bug] "
labels: bug
assignees: ''
---

## Description

A clear and concise description of what the bug is.

## Steps to Reproduce

1. Configure Elite Reasoning MCP in your IDE
2. Send a prompt like: `...`
3. Observe the error in: `...`

## Expected Behavior

What you expected to happen.

## Actual Behavior

What actually happened. Include the full tool output if possible.

## Environment

- **OS:** (e.g., macOS 14.5, Ubuntu 22.04, Windows 11)
- **Python version:** (e.g., 3.11.9)
- **uv version:** (run `uv --version`)
- **IDE:** (e.g., Cursor 0.45, VS Code 1.96, Antigravity, Claude Desktop)
- **MCP SDK version:** (check `pyproject.toml` or `uv pip list`)
- **Elite Reasoning version:** (commit hash or tag)

## MCP Config

Paste your relevant MCP configuration (redact any API keys):

```json
{
  "mcpServers": {
    "elite-reasoning": {
      "command": "..."
    }
  }
}
```

## Logs

<details>
<summary>Server logs</summary>

```
Paste any relevant logs from stderr or the MCP server output here.
Check: ~/.elite-reasoning/brain/elite.db for database errors.
```

</details>

## Additional Context

- Does this happen on every prompt, or only specific ones?
- Did it work before? If so, what changed?
- Are optional dependencies installed? (`sqlite-vec`, `sentence-transformers`)
