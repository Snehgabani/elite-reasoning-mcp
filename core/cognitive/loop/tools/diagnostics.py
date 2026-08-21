"""Diagnostics Tool — System health, metrics, and quality tracking."""

from __future__ import annotations

import json
import time
from typing import Annotated, Any

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from core.cognitive.loop.core.metrics import SCORECARD_DIMENSIONS
from core.cognitive.loop.core.store import SingularityStore

_DIAG_ANNOTATIONS = ToolAnnotations(
    title="View system diagnostics",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

_METRIC_ANNOTATIONS = ToolAnnotations(
    title="Track or view metrics",
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)


class DiagnosticsResult(BaseModel):
    action: str
    data: dict[str, Any] = Field(default_factory=dict)
    interpretation: str = ""


def register(mcp, store: SingularityStore):
    @mcp.tool(name="diagnostics", annotations=_DIAG_ANNOTATIONS)
    def diagnostics(
        action: str = "health",
        days: Annotated[int, Field(default=7, ge=1, le=365)] = 7,
        dimension: Annotated[str, Field(default="")] = "",
    ) -> DiagnosticsResult:
        """View system health, quality trends, tool usage, or scorecard. Actions: health (dependency status), quality (score trends), usage (tool analytics), summary (full overview), scorecard (dimension definitions). Read-only diagnostics. Use to track improvement over time.

        Returns structured data for monitoring reasoning enhancement effectiveness.
        """
        if action == "health":
            import importlib
            checks = []
            try:
                import mcp as _mcp  # noqa
                checks.append({"component": "mcp", "status": "ok", "detail": "MCP SDK available"})
            except ImportError:
                checks.append({"component": "mcp", "status": "error", "detail": "Not found"})
            try:
                import sqlite_vec  # noqa
                checks.append({"component": "sqlite_vec", "status": "ok", "detail": "Vector search available"})
            except ImportError:
                checks.append({"component": "sqlite_vec", "status": "degraded", "detail": "FTS fallback"})
            try:
                summary = store.get_operational_summary(1)
                checks.append({"component": "database", "status": "ok",
                    "detail": f"{summary['memory_items']} memory, {summary['anti_patterns']} anti-patterns"})
            except Exception as e:
                checks.append({"component": "database", "status": "error", "detail": str(e)})
            overall = "healthy" if all(c["status"] == "ok" for c in checks) else "degraded"
            return DiagnosticsResult(action="health",
                data={"status": overall, "checks": checks},
                interpretation=f"Status: {overall}. {len([c for c in checks if c['status'] == 'ok'])}/{len(checks)} healthy.")

        elif action == "quality":
            trend = store.get_quality_trend(dimension=dimension, days=days)
            if trend.get("trend") == "no_data":
                return DiagnosticsResult(action="quality", data=trend,
                    interpretation="No quality data yet. Use reasoning_run to generate scores.")
            return DiagnosticsResult(action="quality", data=trend,
                interpretation=f"Trend: {trend['trend']}. Avg: {trend['average']}/100 over {trend['count']} measurements.")

        elif action == "usage":
            stats = store.get_tool_usage_stats(days=days)
            return DiagnosticsResult(action="usage", data=stats,
                interpretation=f"{stats['total_calls']} calls over {days}d. Total: {stats['total_ms']}ms.")

        elif action == "summary":
            summary = store.get_operational_summary(days=days)
            quality = store.get_quality_trend(days=days)
            calibration = store.get_calibration_score(days=days)
            return DiagnosticsResult(action="summary",
                data={"operational": summary, "quality": quality, "calibration": calibration},
                interpretation=f"{days}d: {summary['sessions']['count']} sessions, {summary['tool_calls']['count']} calls, "
                               f"{summary['memory_items']} memory, {summary['anti_patterns']} anti-patterns.")

        elif action == "variance":
            # v15 P0 #4: variance-aware diagnostics — dispersion of quality
            # scores (std, CV, stability grade), not just point averages.
            # Research base: ACL 2026 reasoning tutorial (consistency across
            # seeds); "Stop Using Temperature 0 for LLM Evals" (temp 0 hides
            # variance). Read-only, deterministic.
            var = store.get_quality_variance(dimension=dimension, days=days)
            if var.get("count", 0) == 0:
                return DiagnosticsResult(action="variance", data=var,
                    interpretation="No quality data in window. Run reasoning_run to seed the variance analysis.")
            return DiagnosticsResult(action="variance", data=var,
                interpretation=var["interpretation"])

        elif action == "scorecard":
            return DiagnosticsResult(action="scorecard",
                data={n: {"weight": c["weight"], "description": c["description"], "benchmarks": c["benchmarks"]}
                      for n, c in SCORECARD_DIMENSIONS.items()},
                interpretation="7-dimension scorecard. task_success (30%) dominates. Total weight = 1.0.")

        return DiagnosticsResult(action=action, interpretation=f"Unknown: {action}. Use health, quality, usage, summary, variance, or scorecard.")

    @mcp.tool(name="metric_track", annotations=_METRIC_ANNOTATIONS)
    def metric_track(
        name: Annotated[str, Field(min_length=1, max_length=128)],
        value: Annotated[float | None, Field()] = None,
        unit: Annotated[str, Field(default="")] = "",
        days: Annotated[int, Field(default=30, ge=1, le=365)] = 30,
    ) -> DiagnosticsResult:
        """Record a custom metric value or view its trend. Provide name+value to record, or name only to view trend. Use for tracking any measurable quantity (latency, accuracy, cost). Skip if not tracking anything specific.

        Metrics persist across sessions for longitudinal analysis.
        """
        # BUGFIX: docs promised name-only trend viewing but the schema required
        # value. Make value optional — None = view trend only, no recording.
        if value is None:
            trend = store.get_metric_trend(name, days=days)
            return DiagnosticsResult(action="metric_track",
                data={"recorded": None, "trend": trend},
                interpretation=f"Trend for {name}: {trend.get('trend', 'N/A')} "
                               f"(latest={trend.get('latest', 'N/A')}, avg={trend.get('average', 'N/A')}, n={trend.get('count', 'N/A')}).")
        store.record_metric(name, value, unit)
        trend = store.get_metric_trend(name, days=days)
        return DiagnosticsResult(action="metric_track",
            data={"recorded": {"name": name, "value": value, "unit": unit}, "trend": trend},
            interpretation=f"Recorded {name}={value} {unit}. Trend: {trend.get('trend', 'N/A')} "
                           f"(latest={trend.get('latest', 'N/A')}, avg={trend.get('average', 'N/A')}).")
