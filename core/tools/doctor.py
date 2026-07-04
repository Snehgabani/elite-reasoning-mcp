"""Release health checks for Elite Reasoning MCP."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

from core.orchestration.capabilities import build_capability_registry

REQUIRED_TABLES = {
    "anti_patterns",
    "decisions",
    "quality_scores",
    "goals",
    "prompt_sessions",
    "prevention_rules",
    "workflow_runs",
    "workflow_steps",
    "memory_items",
}


def _package_version() -> str:
    try:
        return importlib.metadata.version("elite-reasoning-mcp")
    except importlib.metadata.PackageNotFoundError:
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        try:
            for line in pyproject.read_text(encoding="utf-8").splitlines():
                if line.startswith("version = "):
                    return line.split("=", 1)[1].strip().strip('"')
        except OSError:
            pass
    return "unknown"


def _module_available(module: str) -> dict[str, Any]:
    try:
        importlib.import_module(module)
        return {"module": module, "available": True, "status": "installed"}
    except ImportError:
        return {"module": module, "available": False, "status": "missing"}


def _tool_count(mcp) -> int | None:
    if mcp is None:
        return None
    try:
        return len(getattr(getattr(mcp, "_tool_manager"), "_tools"))
    except Exception:
        return None


def _db_tables(store) -> set[str]:
    conn = store._connect()
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')")
    tables = {row[0] for row in c.fetchall()}
    if not getattr(store._local, "in_transaction", False):
        store._close(conn)
    return tables


def build_doctor_report(store, profile=None, mcp=None) -> dict[str, Any]:
    """Return a structured release health report."""
    registry = build_capability_registry()
    tables = _db_tables(store)
    missing_tables = sorted(REQUIRED_TABLES - tables)
    tool_count = _tool_count(mcp)
    profile_ide = getattr(profile, "ide_type", "") if profile is not None else ""
    blockers: list[str] = []
    warnings: list[str] = []

    if missing_tables:
        blockers.append(f"Missing required DB tables: {', '.join(missing_tables)}")
    if not os.path.exists(getattr(store, "db_path", "")):
        blockers.append("elite.db does not exist or is not readable")
    if tool_count is not None and tool_count < 20:
        blockers.append(f"Unexpectedly low MCP tool count: {tool_count}")
    if profile_ide and registry.active_ide and profile_ide != registry.active_ide:
        warnings.append(f"Profile IDE `{profile_ide}` differs from capability registry `{registry.active_ide}`")
    warnings.extend(registry.warnings)

    dependencies = {
        "core": [
            _module_available("mcp"),
            _module_available("fastmcp"),
            _module_available("pydantic"),
            _module_available("httpx"),
        ],
        "optional_vectors": [
            _module_available("sqlite_vec"),
            _module_available("sentence_transformers"),
        ],
        "optional_graph": [
            _module_available("langgraph"),
            _module_available("langchain_core"),
            _module_available("networkx"),
        ],
    }

    score = 100
    score -= 30 * len(blockers)
    score -= 8 * len(warnings)
    if any(not item["available"] for item in dependencies["core"]):
        score -= 40
    score = max(0, min(100, score))
    status = "release_ready" if score >= 90 and not blockers else "degraded" if score >= 70 else "blocked"

    return {
        "status": status,
        "release_readiness_score": score,
        "version": _package_version(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "brain_dir": getattr(store, "brain_dir", ""),
        "db_path": getattr(store, "db_path", ""),
        "db_exists": os.path.exists(getattr(store, "db_path", "")),
        "required_tables_present": not missing_tables,
        "missing_tables": missing_tables,
        "tool_count": tool_count,
        "active_ide": registry.active_ide,
        "profile_ide": profile_ide or None,
        "recommendable_mcps": registry.names("mcp")[:25],
        "recommendable_skills": registry.names("skill")[:25],
        "dependencies": dependencies,
        "blockers": blockers,
        "warnings": warnings,
    }


def doctor_markdown(report: dict[str, Any]) -> str:
    """Render the doctor report as Markdown plus JSON."""
    lines = [
        "# Elite MCP Doctor",
        "",
        f"**Status:** `{report['status']}`",
        f"**Release readiness:** {report['release_readiness_score']}/100",
        f"**Version:** `{report['version']}`",
        f"**Python:** `{report['python']}`",
        f"**Active IDE:** `{report['active_ide']}`",
        f"**Tool count:** {report['tool_count'] if report['tool_count'] is not None else 'unknown'}",
        f"**DB:** `{report['db_path']}`",
        "",
    ]
    if report["blockers"]:
        lines.append("## Blockers")
        lines.extend(f"- {item}" for item in report["blockers"])
        lines.append("")
    if report["warnings"]:
        lines.append("## Warnings")
        lines.extend(f"- {item}" for item in report["warnings"])
        lines.append("")

    lines.append("## Dependencies")
    for group, deps in report["dependencies"].items():
        summary = ", ".join(f"{item['module']}={item['status']}" for item in deps)
        lines.append(f"- `{group}`: {summary}")

    lines.extend(["", "## JSON", "```json", json.dumps(report, indent=2, sort_keys=True), "```"])
    return "\n".join(lines)


def register(mcp, store, profile=None):
    """Register release doctor tools."""

    @mcp.tool()
    def elite_doctor(output_format: str = "markdown") -> str:
        """Run a release-readiness health check for this MCP server.

        Args:
            output_format: markdown or json.
        """
        report = build_doctor_report(store, profile=profile, mcp=mcp)
        if output_format.lower() == "json":
            return json.dumps(report, indent=2, sort_keys=True)
        return doctor_markdown(report)

    @mcp.tool()
    def elite_doctor_json() -> dict[str, Any]:
        """Return a structured release-readiness health report."""
        return build_doctor_report(store, profile=profile, mcp=mcp)
