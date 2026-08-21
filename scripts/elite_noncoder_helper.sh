#!/usr/bin/env bash
# Elite Reasoning MCP: One-Click Non-Coder AI Contract & Verification Tool

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

export PYTHONPATH="${ROOT_DIR}"

if command -v uv >/dev/null 2>&1; then
    uv run python3 -m core.cli.noncoder interactive
elif command -v python3 >/dev/null 2>&1; then
    python3 -m core.cli.noncoder interactive
else
    echo "❌ Error: Python 3 or uv is required to run Elite Assistant."
    exit 1
fi
