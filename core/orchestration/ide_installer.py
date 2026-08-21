"""Previewable, atomic MCP configuration installer for supported IDEs."""

from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class IDEConfigTarget:
    name: str
    config_path: Path
    config_type: str  # "mcpServers" | "context_servers"


class IDEConfigError(ValueError):
    """Raised when an existing IDE config cannot be updated safely."""


class MultiIDEInstaller:
    """Build and atomically install MCP connection configuration."""

    def __init__(self, binary_path: Optional[str] = None):
        self.home = Path.home()
        if binary_path:
            self.binary_path = binary_path
        else:
            default_path = str(self.home / ".local/share/uv/tools/elite-reasoning-mcp/bin/elite-reasoning-mcp")
            self.binary_path = (
                default_path if os.path.exists(default_path) else shutil.which("elite-reasoning-mcp") or default_path
            )

    def get_ide_targets(self) -> List[IDEConfigTarget]:
        return [
            IDEConfigTarget(
                name="Claude Desktop",
                config_path=self.home / "Library/Application Support/Claude/claude_desktop_config.json",
                config_type="mcpServers",
            ),
            IDEConfigTarget(name="Cursor", config_path=self.home / ".cursor/mcp.json", config_type="mcpServers"),
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

    def target_for(self, name: str) -> IDEConfigTarget:
        normalized = (name or "").strip().lower().replace("-", " ").replace("_", " ")
        aliases = {"claude": "claude desktop", "gemini": "antigravity"}
        normalized = aliases.get(normalized, normalized)
        for target in self.get_ide_targets():
            if target.name.lower() == normalized:
                return target
        choices = ", ".join(target.name for target in self.get_ide_targets())
        raise IDEConfigError(f"unsupported IDE {name!r}; choose one of: {choices}")

    def _load(self, target: IDEConfigTarget) -> Dict[str, Any]:
        if not target.config_path.exists():
            return {}
        try:
            parsed = json.loads(target.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IDEConfigError(f"refusing to overwrite unreadable JSON config: {target.config_path}") from exc
        if not isinstance(parsed, dict):
            raise IDEConfigError(f"IDE config root must be a JSON object: {target.config_path}")
        return parsed

    def render_target(self, target: IDEConfigTarget) -> Dict[str, Any]:
        current = self._load(target)
        entry = {
            "command": self.binary_path,
            "args": [],
            "env": {
                "ELITE_TOOL_PROFILE": "core",
                "PYTHONUNBUFFERED": "1",
            },
        }
        if target.config_type == "mcpServers":
            servers = current.setdefault("mcpServers", {})
            if not isinstance(servers, dict):
                raise IDEConfigError(f"mcpServers must be a JSON object: {target.config_path}")
            servers["elite-reasoning"] = entry
        elif target.config_type == "context_servers":
            servers = current.setdefault("context_servers", {})
            if not isinstance(servers, dict):
                raise IDEConfigError(f"context_servers must be a JSON object: {target.config_path}")
            servers["elite-reasoning"] = {
                "command": {
                    "path": self.binary_path,
                    "args": [],
                    "env": {"ELITE_TOOL_PROFILE": "core", "PYTHONUNBUFFERED": "1"},
                }
            }
        else:
            raise IDEConfigError(f"unsupported config type: {target.config_type}")
        return current

    def preview_target(self, target: IDEConfigTarget) -> Dict[str, Any]:
        return {
            "ide": target.name,
            "path": str(target.config_path),
            "status": "preview",
            "config": self.render_target(target),
        }

    def install_to_target(self, target: IDEConfigTarget) -> Dict[str, Any]:
        rendered = self.render_target(target)
        target.config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary_name = tempfile.mkstemp(
            prefix=target.config_path.name + ".", suffix=".tmp", dir=target.config_path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(rendered, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
            os.replace(temporary, target.config_path)
        finally:
            temporary.unlink(missing_ok=True)
        return {"ide": target.name, "path": str(target.config_path), "status": "installed"}

    def install_all(self) -> List[Dict[str, Any]]:
        return [self.install_to_target(target) for target in self.get_ide_targets()]
