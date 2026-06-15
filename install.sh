#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║  Elite Reasoning MCP — One-Command Installer                ║
# ║  Makes any LLM think harder, reason better, never repeat    ║
# ║  mistakes. 66 tools. Works with any IDE + any model.        ║
# ╚══════════════════════════════════════════════════════════════╝
#
# USAGE:
#   curl -fsSL https://raw.githubusercontent.com/YOUR_REPO/main/install.sh | bash
#   — OR —
#   bash install.sh
#
set -euo pipefail

ELITE_DIR="$HOME/.elite-reasoning"
BRAIN_DIR="$ELITE_DIR/brain"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  🧠 Elite Reasoning MCP — Installer          ║"
echo "║  66 tools · Works with any model             ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Step 1: Check prerequisites ────────────────────────
echo "→ Checking prerequisites..."
if ! command -v uv &>/dev/null; then
    echo "  Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "  ✅ uv ready"

# ── Step 2: Clone elite-system ─────────────────────────
echo "→ Setting up Elite Reasoning MCP..."
mkdir -p "$BRAIN_DIR"

if [ -n "${ELITE_REPO_URL:-}" ]; then
    git clone "$ELITE_REPO_URL" "$ELITE_DIR" 2>/dev/null || (cd "$ELITE_DIR" && git pull --ff-only)
fi
chmod +x "$ELITE_DIR/run_elite_mcp.sh" 2>/dev/null || true

# ── Step 3: Configure IDE ─────────────────────────────
echo "→ Configuring IDE..."
GEMINI_CONFIG="$HOME/.gemini/config"
MCP_CONFIG="$GEMINI_CONFIG/mcp_config.json"
mkdir -p "$GEMINI_CONFIG"

if [ -f "$MCP_CONFIG" ]; then
    if ! grep -q "elite-reasoning" "$MCP_CONFIG"; then
        python3 -c "
import json
with open('$MCP_CONFIG') as f: c = json.load(f)
c['mcpServers']['elite-reasoning'] = {'command': '$ELITE_DIR/run_elite_mcp.sh'}
with open('$MCP_CONFIG', 'w') as f: json.dump(c, f, indent=2)
"
    fi
fi

# Add enforcement to GEMINI.md
GEMINI_MD="$HOME/.gemini/GEMINI.md"
if ! grep -q "orchestrate_request_tool" "$GEMINI_MD" 2>/dev/null; then
    cat >> "$GEMINI_MD" << 'EOF'

# Global Instructions

## ⚡ RULE #0 — ELITE MCP PIPELINE

On EVERY user message, your FIRST tool call MUST be:

```
call_mcp_tool(
  ServerName="elite-reasoning",
  ToolName="orchestrate_request_tool",
  Arguments={"user_prompt": "<the user's exact message>"}
)
```

No exceptions except "ok", "thanks", "yes", "no". This fires the 66-tool reasoning pipeline.
EOF
fi

echo ""
echo "✅ Done! Restart your IDE and start a new conversation."
echo "   Every prompt will now go through the elite reasoning pipeline."
