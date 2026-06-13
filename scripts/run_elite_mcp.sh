#!/bin/bash
# Elite MCP Server — Portable Launcher
# Works for ANY user on ANY machine. Uses $HOME-relative paths.
# Each user gets their own brain directory and personalized orchestration.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Per-user brain directory (isolated data per user)
BRAIN_DIR="${ELITE_BRAIN_DIR:-$SCRIPT_DIR/brain}"
mkdir -p "$BRAIN_DIR"

# Log file
LOG_FILE="$SCRIPT_DIR/mcp_error.log"

# Auto-detect uv binary
if command -v uv &>/dev/null; then
    UV_BIN="uv"
elif [ -f "$HOME/.gemini/antigravity/bin/uv" ]; then
    UV_BIN="$HOME/.gemini/antigravity/bin/uv"
elif [ -f "$HOME/.local/bin/uv" ]; then
    UV_BIN="$HOME/.local/bin/uv"
else
    echo "ERROR: uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

exec "$UV_BIN" run --with mcp --with fastmcp python -c "
import sys; sys.path.append('.')
from core.integration.mcp_server import create_mcp_server
server = create_mcp_server('$BRAIN_DIR')
server.run()
" 2>> "$LOG_FILE"
