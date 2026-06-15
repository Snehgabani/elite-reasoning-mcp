#!/bin/bash
cd /Users/snehgabani/.gemini/antigravity/scratch/elite-system

# Load python env and run the sync server
export ELITE_CENTRAL_DIR="brain_central"
export SYNC_PORT=8000

echo "🚀 Starting Elite Team Sync Hub on port $SYNC_PORT..."
/Users/snehgabani/.gemini/antigravity/bin/uv run --with fastapi --with uvicorn python core/integration/sync_server.py
