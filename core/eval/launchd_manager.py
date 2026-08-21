"""
macOS LaunchAgent Manager for Elite Reasoning MCP Background Daemons.
Provides native 0MB idle memory background task execution via launchd.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


class LaunchdManager:
    """Manages creation, installation, and inspection of macOS LaunchAgent services."""

    PLIST_LABEL = "com.sovereign.elite-benchmark"

    def __init__(self, home: Optional[Path] = None):
        self.home = home or Path.home()
        self.launch_agents_dir = self.home / "Library/LaunchAgents"
        self.plist_path = self.launch_agents_dir / f"{self.PLIST_LABEL}.plist"
        self.binary_path = str(self.home / ".local/share/uv/tools/elite-reasoning-mcp/bin/elite-reasoning-mcp")
        if not os.path.exists(self.binary_path):
            found = shutil.which("elite-reasoning-mcp")
            if found:
                self.binary_path = found

    def generate_plist_content(self, interval_seconds: int = 86400) -> str:
        """Generates XML plist specification for launchd."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{self.PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{self.binary_path}</string>
        <string>benchmark</string>
        <string>--split</string>
        <string>all</string>
    </array>
    <key>StartInterval</key>
    <integer>{interval_seconds}</integer>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>{str(self.home)}/.elite-reasoning/logs/benchmark_daemon.log</string>
    <key>StandardErrorPath</key>
    <string>{str(self.home)}/.elite-reasoning/logs/benchmark_daemon.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>ELITE_ALLOW_CROSS_IDE_SKILLS</key>
        <string>1</string>
    </dict>
</dict>
</plist>
"""

    def install(self, interval_seconds: int = 86400) -> Dict[str, Any]:
        """Writes plist and loads service via launchctl."""
        self.launch_agents_dir.mkdir(parents=True, exist_ok=True)
        (self.home / ".elite-reasoning/logs").mkdir(parents=True, exist_ok=True)

        plist_text = self.generate_plist_content(interval_seconds)
        self.plist_path.write_text(plist_text, encoding="utf-8")

        # Unload if already loaded, then load
        subprocess.run(["launchctl", "unload", str(self.plist_path)], capture_output=True)
        res = subprocess.run(["launchctl", "load", str(self.plist_path)], capture_output=True, text=True)

        return {
            "status": "installed",
            "label": self.PLIST_LABEL,
            "plist_path": str(self.plist_path),
            "loaded": res.returncode == 0,
        }

    def status(self) -> Dict[str, Any]:
        """Checks service registration status."""
        res = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        is_running = self.PLIST_LABEL in res.stdout
        return {
            "label": self.PLIST_LABEL,
            "installed": self.plist_path.exists(),
            "active_in_launchd": is_running,
            "plist_path": str(self.plist_path),
        }
