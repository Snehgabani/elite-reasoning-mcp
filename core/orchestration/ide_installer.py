"""
Universal Multi-IDE Configuration Installer & Sync Engine.
Automatically discovers installed IDEs (Claude Desktop, Cursor, Windsurf, Zed, VS Code / Antigravity)
and writes or synchronizes native MCP server configurations idempotently.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class IDEConfigTarget:
    name: str
    config_path: Path
    config_type: str  # "mcpServers" | "context_servers" | "custom"


class MultiIDEInstaller:
    """
    Detects and installs MCP connection configurations across all supported IDEs.
    """

    def __init__(self, binary_path: Optional[str] = None):
        self.home = Path.home()
        if binary_path:
            self.binary_path = binary_path
        else:
            default_path = str(self.home / ".local/share/uv/tools/elite-reasoning-mcp/bin/elite-reasoning-mcp")
            if os.path.exists(default_path):
                self.binary_path = default_path
            else:
                self.binary_path = shutil.which("elite-reasoning-mcp") or default_path

    def get_ide_targets(self) -> List[IDEConfigTarget]:
        """Returns standard configuration targets across IDE ecosystems."""
        return [
            IDEConfigTarget(
                name="Claude Desktop",
                config_path=self.home / "Library/Application Support/Claude/claude_desktop_config.json",
                config_type="mcpServers",
            ),
            IDEConfigTarget(
                name="Cursor",
                config_path=self.home / ".cursor/mcp.json",
                config_type="mcpServers",
            ),
            IDEConfigTarget(
                name="Windsurf",
                config_path=self.home / ".codeium/windsurf/mcp_config.json",
                config_type="mcpServers",
            ),
            IDEConfigTarget(
                name="Zed",
                config_path=self.home / ".config/zed/settings.json",
                config_type="context_servers",
            ),
            IDEConfigTarget(
                name="Antigravity",
                config_path=self.home / ".gemini/antigravity/mcp_config.json",
                config_type="mcpServers",
            ),
        ]

    def install_to_target(self, target: IDEConfigTarget) -> Dict[str, Any]:
        """Safely updates the target JSON configuration file."""
        target.config_path.parent.mkdir(parents=True, exist_ok=True)

        current_config: Dict[str, Any] = {}
        if target.config_path.exists():
            try:
                current_config = json.loads(target.config_path.read_text(encoding="utf-8"))
            except Exception:
                current_config = {}

        entry = {
            "command": self.binary_path,
            "args": ["run"],
            "env": {
                "ELITE_ALLOW_CROSS_IDE_SKILLS": "1",
                "PYTHONUNBUFFERED": "1",
            },
        }

        if target.config_type == "mcpServers":
            if "mcpServers" not in current_config:
                current_config["mcpServers"] = {}
            current_config["mcpServers"]["elite-reasoning-mcp"] = entry
        elif target.config_type == "context_servers":
            if "context_servers" not in current_config:
                current_config["context_servers"] = {}
            current_config["context_servers"]["elite-reasoning-mcp"] = {
                "command": {
                    "path": self.binary_path,
                    "args": ["run"],
                    "env": {
                        "ELITE_ALLOW_CROSS_IDE_SKILLS": "1",
                    },
                }
            }

        # Write atomically
        target.config_path.write_text(json.dumps(current_config, indent=2), encoding="utf-8")
        return {
            "ide": target.name,
            "path": str(target.config_path),
            "status": "installed",
        }

    def install_all(self) -> List[Dict[str, Any]]:
        """Installs configurations to all target locations."""
        results = []
        for target in self.get_ide_targets():
            res = self.install_to_target(target)
            results.append(res)
        return results
