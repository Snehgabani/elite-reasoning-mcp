"""Capability discovery and verification for MCP/Skill routing.

The orchestrator should recommend what the active IDE can actually expose,
not merely what exists in another tool's config directory. This module builds a
small, explainable capability registry across Zed settings, legacy IDE folders,
and explicit environment overrides.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

CapabilityKind = Literal["mcp", "skill"]
CapabilityStatus = Literal["verified", "configured", "discovered", "unverified", "unavailable"]


@dataclass(frozen=True)
class Capability:
    """A routable MCP server or skill with provenance and confidence."""

    name: str
    kind: CapabilityKind
    source: str
    status: CapabilityStatus
    confidence: float
    reason: str
    command: str = ""
    url: str = ""
    tools: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_recommendable(self) -> bool:
        """Whether the orchestrator may safely recommend this capability."""
        return self.status in {"verified", "configured", "discovered"} and self.confidence >= 0.5


@dataclass(frozen=True)
class CapabilityRegistry:
    """A point-in-time capability snapshot."""

    capabilities: tuple[Capability, ...]
    active_ide: str
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def by_kind(self, kind: CapabilityKind, recommendable_only: bool = True) -> list[Capability]:
        caps = [cap for cap in self.capabilities if cap.kind == kind]
        if recommendable_only:
            caps = [cap for cap in caps if cap.is_recommendable]
        return sorted(caps, key=lambda c: (-c.confidence, c.name))

    def names(self, kind: CapabilityKind, recommendable_only: bool = True) -> list[str]:
        return [cap.name for cap in self.by_kind(kind, recommendable_only)]


# ── JSONC parsing for Zed settings ───────────────────────────


def _strip_jsonc_comments(text: str) -> str:
    """Remove // and /* */ comments while preserving quoted strings."""
    out: list[str] = []
    i = 0
    in_string = False
    escape = False
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue

        if ch == "/" and nxt == "/":
            i += 2
            while i < len(text) and text[i] not in "\r\n":
                i += 1
            continue

        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue

        out.append(ch)
        i += 1
    return "".join(out)


def parse_jsonc(text: str) -> dict[str, Any]:
    """Parse the JSONC subset used by Zed settings.

    This intentionally supports comments and trailing commas, not arbitrary JSON5.
    """
    stripped = _strip_jsonc_comments(text)
    stripped = re.sub(r",\s*([}\]])", r"\1", stripped)
    if not stripped.strip():
        return {}
    data = json.loads(stripped)
    return data if isinstance(data, dict) else {}


def load_zed_settings(settings_path: str | None = None) -> dict[str, Any]:
    """Load Zed settings as JSONC. Returns {} on missing/invalid files."""
    path = Path(settings_path).expanduser() if settings_path else Path.home() / ".config" / "zed" / "settings.json"
    if not path.exists():
        return {}
    try:
        return parse_jsonc(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def scan_zed_context_servers(settings_path: str | None = None) -> list[Capability]:
    """Discover MCP context servers configured for Zed."""
    settings = load_zed_settings(settings_path)
    servers = settings.get("context_servers", {})
    if not isinstance(servers, dict):
        return []

    capabilities: list[Capability] = []
    for name, config in sorted(servers.items()):
        if not isinstance(config, dict):
            continue
        enabled = config.get("enabled", True)
        if enabled is False:
            status: CapabilityStatus = "unavailable"
            confidence = 0.0
            reason = "Configured in Zed but disabled."
        else:
            status = "configured"
            confidence = 0.85
            reason = "Configured in Zed context_servers; Zed should expose this after server startup."

        command_value = config.get("command", "")
        command = ""
        if isinstance(command_value, str):
            command = command_value
        elif isinstance(command_value, dict):
            command = str(command_value.get("path", ""))

        url = str(config.get("url", "")) if config.get("url") else ""
        warnings: list[str] = []
        if status == "configured" and not command and not url and config.get("remote") is not False:
            warnings.append("No command/url found; this may rely on a Zed extension registry entry.")

        capabilities.append(
            Capability(
                name=name,
                kind="mcp",
                source="zed_settings",
                status=status,
                confidence=confidence,
                reason=reason,
                command=command,
                url=url,
                warnings=tuple(warnings),
            )
        )
    return capabilities


# ── Legacy / portable discovery ──────────────────────────────


def _split_env_list(value: str | None) -> list[str]:
    if not value:
        return []
    return sorted({item.strip() for item in value.split(",") if item.strip()})


def _scan_dirs_for_children(paths: Iterable[Path]) -> list[str]:
    names: set[str] = set()
    for path in paths:
        if not path.exists() or not path.is_dir():
            continue
        for child in path.iterdir():
            if child.is_dir():
                names.add(child.name)
    return sorted(names)


def _scan_legacy_mcp_names() -> list[str]:
    home = Path.home()
    explicit = os.environ.get("ELITE_MCP_DIR")
    paths = (
        [Path(explicit).expanduser()]
        if explicit
        else [
            home / ".gemini" / "antigravity" / "mcp",
            home / ".gemini" / "mcp",
            home / ".vscode" / "mcp",
            home / ".cursor" / "mcp",
        ]
    )
    return _scan_dirs_for_children(paths)


def _scan_legacy_skill_names() -> list[str]:
    home = Path.home()
    explicit = os.environ.get("ELITE_SKILLS_DIR")
    plugin_roots = (
        [Path(explicit).expanduser()]
        if explicit
        else [
            home / ".gemini" / "config" / "plugins",
            home / ".gemini" / "plugins",
        ]
    )
    names: set[str] = set()
    for root in plugin_roots:
        if not root.exists() or not root.is_dir():
            continue
        for plugin in root.iterdir():
            skills_root = plugin / "skills"
            if skills_root.is_dir():
                for skill in skills_root.iterdir():
                    if skill.is_dir():
                        names.add(skill.name)
    return sorted(names)


def _capabilities_from_names(
    names: Iterable[str], kind: CapabilityKind, source: str, confidence: float
) -> list[Capability]:
    status: CapabilityStatus = "verified" if source.startswith("env") else "discovered"
    reason = (
        "Explicitly provided by environment override."
        if source.startswith("env")
        else "Discovered on disk; may not be exposed to the active IDE agent."
    )
    return [
        Capability(name=name, kind=kind, source=source, status=status, confidence=confidence, reason=reason)
        for name in sorted(set(names))
    ]


def build_capability_registry(settings_path: str | None = None) -> CapabilityRegistry:
    """Build a capability registry with active-IDE-aware precedence.

    Environment overrides:
    - ELITE_VISIBLE_MCPS: comma-separated MCPs known visible to the current agent
    - ELITE_VISIBLE_SKILLS: comma-separated skills known visible to the current agent
    - ELITE_ACTIVE_IDE: explicit active IDE name, e.g. zed/gemini/cursor
    - ELITE_ALLOW_CROSS_IDE_SKILLS=1: allow legacy skill discovery while Zed is active
    """
    warnings: list[str] = []
    capabilities: list[Capability] = []

    env_mcps = _split_env_list(os.environ.get("ELITE_VISIBLE_MCPS"))
    env_skills = _split_env_list(os.environ.get("ELITE_VISIBLE_SKILLS"))
    capabilities.extend(_capabilities_from_names(env_mcps, "mcp", "env_visible", 1.0))
    capabilities.extend(_capabilities_from_names(env_skills, "skill", "env_visible", 1.0))

    zed_caps = scan_zed_context_servers(settings_path)
    capabilities.extend(zed_caps)

    explicit_ide = os.environ.get("ELITE_ACTIVE_IDE", "").strip().lower()
    active_ide = explicit_ide or ("zed" if zed_caps else "portable")

    # Only use cross-IDE skill folders by default when Zed is not active. This
    # prevents the orchestrator from recommending Gemini/Antigravity skills that
    # the Zed agent cannot actually invoke.
    allow_cross_ide_skills = os.environ.get("ELITE_ALLOW_CROSS_IDE_SKILLS") == "1"

    legacy_mcps = _scan_legacy_mcp_names()
    known_mcp_names = {cap.name for cap in capabilities if cap.kind == "mcp"}
    capabilities.extend(
        _capabilities_from_names(
            [name for name in legacy_mcps if name not in known_mcp_names],
            "mcp",
            "legacy_ide_directory",
            0.55 if active_ide != "zed" else 0.35,
        )
    )

    if active_ide != "zed" or allow_cross_ide_skills or env_skills:
        legacy_skills = _scan_legacy_skill_names()
        known_skill_names = {cap.name for cap in capabilities if cap.kind == "skill"}
        capabilities.extend(
            _capabilities_from_names(
                [name for name in legacy_skills if name not in known_skill_names],
                "skill",
                "legacy_ide_directory",
                0.60 if active_ide != "zed" else 0.35,
            )
        )
    elif zed_caps:
        warnings.append(
            "Zed is active; legacy Gemini/Antigravity skills are suppressed unless "
            "ELITE_ALLOW_CROSS_IDE_SKILLS=1 or ELITE_VISIBLE_SKILLS is set."
        )

    if not capabilities:
        warnings.append("No MCP/skill capabilities discovered. Configure context_servers or ELITE_VISIBLE_* env vars.")

    return CapabilityRegistry(capabilities=tuple(capabilities), active_ide=active_ide, warnings=tuple(warnings))


def format_capability_report(registry: CapabilityRegistry) -> str:
    """Render a human-readable capability report for MCP users."""
    lines = [
        "# Capability Verification Report",
        "",
        f"**Active IDE:** `{registry.active_ide}`",
        f"**Recommendable MCPs:** {len(registry.by_kind('mcp'))}",
        f"**Recommendable Skills:** {len(registry.by_kind('skill'))}",
        "",
    ]

    if registry.warnings:
        lines.append("## Warnings")
        lines.extend(f"- ⚠️ {warning}" for warning in registry.warnings)
        lines.append("")

    sections: tuple[tuple[CapabilityKind, str], ...] = (("mcp", "MCP Servers"), ("skill", "Skills"))
    for kind, title in sections:
        caps = registry.by_kind(kind, recommendable_only=False)
        lines.append(f"## {title}")
        if not caps:
            lines.append("- None discovered.")
            lines.append("")
            continue
        lines.append("| Name | Status | Confidence | Source | Notes |")
        lines.append("|---|---:|---:|---|---|")
        for cap in caps:
            note_parts = [cap.reason]
            if cap.command:
                note_parts.append(f"command: `{cap.command}`")
            if cap.url:
                note_parts.append(f"url: `{cap.url}`")
            note_parts.extend(cap.warnings)
            lines.append(
                f"| `{cap.name}` | {cap.status} | {cap.confidence:.2f} | `{cap.source}` | {' '.join(note_parts)} |"
            )
        lines.append("")

    return "\n".join(lines).strip()
