# src/leverage/telemetry.py
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
METRICS_FILE = Path(PROJECT_ROOT) / ".ai" / "metrics" / "tool_usage.jsonl"


def log_tool_usage(
    tool_name: str,
    start_time: float,
    success: bool,
    tokens_used: int = 0,
    task_id: str = "default",
    error: Optional[str] = None,
):
    """Logs MCP tool usage with task_id for Proof-of-Work telemetry gating.

    Schema is ADDITIVE: existing keys (timestamp, task_id, tool,
    duration_seconds, success, tokens_used) are unchanged; failure rows
    additionally carry an optional short `error` string. tokens_used is
    recorded verbatim (0 when the tool does not expose usage stats).
    """
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "task_id": task_id,
        "tool": tool_name,
        "duration_seconds": round(time.time() - start_time, 2),
        "success": success,
        "tokens_used": tokens_used,
    }
    if error is not None:
        entry["error"] = str(error)[:400]
    with open(METRICS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
