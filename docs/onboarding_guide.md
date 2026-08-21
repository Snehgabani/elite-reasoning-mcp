# 🚀 Elite Reasoning MCP: 5-Minute Design-Partner Onboarding Guide

Welcome to the **Elite Reasoning MCP Design-Partner Program**.

Elite is a **deterministic local contract and evidence gate** for coding agents. It prevents missed requirements, out-of-scope file modifications, and unverified completion claims without sending your code or prompts to any external cloud.

---

## ⚡ 1. Rapid Installation (30 Seconds)

Ensure Python 3.11+ and `uv` or `pip` are installed:

```bash
uv tool install elite-reasoning-mcp
# or
pip install elite-reasoning-mcp
```

---

## 🔍 2. Verify System Invariants (10 Seconds)

Run the deterministic local diagnostics:

```bash
elite-reasoning-mcp doctor
```

Verify that all deterministic gates (AST Gating, Memory Limits, SQLite Store) display **`PASS`**.

---

## 🎯 3. Run the Deterministic Offline Demo (20 Seconds)

```bash
elite-reasoning-mcp demo
```

The demo runs locally in $<1	ext{ms}$ with zero network requests:
1. Compiles explicit user constraints into a `TaskContract`.
2. Tests a defective draft and catches exact failures.
3. Tests a corrected draft and issues verifiable `PASS` verdicts.

---

## 🔌 4. Connect to Your Coding Agent (60 Seconds)

### Cursor (`~/.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "elite-reasoning": {
      "command": "elite-reasoning-mcp",
      "args": ["serve"]
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "elite-reasoning": {
      "command": "elite-reasoning-mcp",
      "args": ["serve"]
    }
  }
}
```

---

## 🛡️ 5. What Elite Guarantees

| Capability | Guarantee |
| :--- | :--- |
| **Contract Compiler** | Extracted requirements link directly to exact source character spans in your instructions. |
| **Evidence Gate** | Four-state verification (`PASS`, `FAIL`, `UNKNOWN`, `NOT_CHECKED`). Stale evidence is rejected. |
| **Trusted Memory** | Zero unverified lessons. Zero secret retention. Strict per-project isolation. |
| **Local Privacy** | Zero cloud telemetry. Everything runs on your machine within $<75	ext{MB}$ RAM. |
