#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export ELITE_TOOL_PROFILE="${ELITE_TOOL_PROFILE:-legacy}"
BRAIN_DIR="${ELITE_BRAIN_DIR:-$SCRIPT_DIR/brain}"
mkdir -p "$BRAIN_DIR"
LOG_FILE="$SCRIPT_DIR/mcp_error.log"

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

CRASH_COUNT=0
LAST_CRASH_TIME=$(date +%s)

while true; do
    "$UV_BIN" run --with mcp --with fastmcp python -c "
import sys; sys.path.append('.')
from core.integration.mcp_server import create_mcp_server
server = create_mcp_server('$BRAIN_DIR')
server.run()
" 2>> "$LOG_FILE"
    
    NOW=$(date +%s)
    if [ $((NOW - LAST_CRASH_TIME)) -lt 10 ]; then
        CRASH_COUNT=$((CRASH_COUNT + 1))
    else
        CRASH_COUNT=1
    fi
    LAST_CRASH_TIME=$NOW

    # Exponential backoff maxing at 60s to prevent spin loops & CPU pegging
    if [ $CRASH_COUNT -gt 5 ]; then
        echo "[$(date)] CRITICAL: Elite MCP crash loop detected. Throttling restarts to 60s." >> "$LOG_FILE"
        sleep 60
    else
        echo "[$(date)] Elite reasoning MCP crashed (Count: $CRASH_COUNT). Auto-restarting in 2 seconds..." >> "$LOG_FILE"
        sleep 2
    fi
done
