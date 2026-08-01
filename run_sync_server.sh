#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Keep sync data local to this checkout unless the operator overrides it.
export ELITE_CENTRAL_DIR="${ELITE_CENTRAL_DIR:-$ROOT_DIR/brain_central}"
export SYNC_PORT="${SYNC_PORT:-8000}"

echo "Starting Elite Team Sync Hub on port $SYNC_PORT..."
exec uv run --with fastapi --with uvicorn python core/integration/sync_server.py
