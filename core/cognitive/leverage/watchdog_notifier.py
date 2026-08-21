"""
macOS Watchdog Notifier & Telemetry Gateway.
Publishes real-time task progress to ~/.elite-reasoning/brain/live_status.json
and triggers native macOS notifications for milestone completions or invariant blocks.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any, Dict


from core.logging_config import get_logger

logger = get_logger(__name__)

BRAIN_DIR = os.environ.get("ELITE_BRAIN_DIR", os.path.expanduser("~/.elite-reasoning/brain"))
LIVE_STATUS_FILE = os.path.join(BRAIN_DIR, "live_status.json")


class WatchdogNotifier:
    """
    Zero-RAM background telemetry logger and macOS desktop notification emitter.
    """

    def __init__(self):
        os.makedirs(BRAIN_DIR, exist_ok=True)

    def notify(self, title: str, message: str, subtitle: str = "Elite Reasoning"):
        """
        Sends native macOS notification banner via osascript.
        """
        if sys.platform == "darwin":
            sub_clause = f'subtitle "{subtitle}"' if subtitle else ""
            clean_msg = message.replace('"', '\\"').replace("'", "")
            clean_title = title.replace('"', '\\"').replace("'", "")
            script = f'display notification "{clean_msg}" with title "{clean_title}" {sub_clause}'
            try:
                subprocess.Popen(
                    ["osascript", "-e", script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                logger.debug("Desktop notification skipped: %s", exc)

    def record_telemetry(
        self,
        task_id: str,
        status: str,
        current_node: str,
        progress_pct: int,
        prm_score: float = 1.0,
        details: str = "",
        notify_desktop: bool = False,
    ) -> Dict[str, Any]:
        """
        Persists live task heartbeat for the macOS watchdog daemon (sovereign-watcher).
        """
        payload = {
            "task_id": task_id,
            "status": status,
            "current_node": current_node,
            "progress_pct": min(100, max(0, progress_pct)),
            "prm_score": prm_score,
            "details": details,
            "timestamp_unix": int(time.time()),
        }

        try:
            with open(LIVE_STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except OSError as exc:
            logger.debug("Live status telemetry persistence skipped: %s", exc)

        if notify_desktop or status in {"ATTESTED_COMPLETE", "INVARIANT_VIOLATION", "DEADLOCK_HALT"}:
            msg = f"{status}: {details[:80]}" if details else f"Task progress: {progress_pct}%"
            self.notify(title="Elite Reasoning Watchdog", message=msg, subtitle=task_id[:20])

        return {
            "status": "TELEMETRY_RECORDED",
            "task_id": task_id,
            "live_status_file": LIVE_STATUS_FILE,
            "desktop_notified": notify_desktop,
        }


_WATCHDOG_NOTIFIER = WatchdogNotifier()

__all__ = ["WatchdogNotifier", "_WATCHDOG_NOTIFIER", "BRAIN_DIR", "LIVE_STATUS_FILE"]
