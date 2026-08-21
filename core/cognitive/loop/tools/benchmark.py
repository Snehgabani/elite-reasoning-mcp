"""Benchmark Tool — A/B eval comparison with Cohen's d effect size."""

from __future__ import annotations

import time
from typing import Annotated, Any

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from core.cognitive.loop.core.metrics import compare_variants, score_output_quality
from core.cognitive.loop.core.store import SingularityStore

_BENCH_ANNOTATIONS = ToolAnnotations(
    title="Run A/B evaluation",
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)


class BenchmarkResult(BaseModel):
    action: str
    eval_name: str
    data: dict[str, Any] = Field(default_factory=dict)
    comparison: dict[str, Any] = Field(default_factory=dict)
    interpretation: str = ""


def register(mcp, store: SingularityStore):
    @mcp.tool(name="benchmark", annotations=_BENCH_ANNOTATIONS)
    def benchmark(
        action: str = "score",
        eval_name: Annotated[str, Field(default="default")] = "default",
        variant: Annotated[str, Field(default="enhanced")] = "enhanced",
        prompt: Annotated[str, Field(default="", max_length=4000)] = "",
        output: Annotated[str, Field(default="", max_length=8000)] = "",
        validation_passed: bool | None = None,
        tool_calls: Annotated[int, Field(default=0, ge=0)] = 0,
        evidence_sources: Annotated[int, Field(default=0, ge=0)] = 0,
        confidence: Annotated[float, Field(default=0.7, ge=0.0, le=1.0)] = 0.7,
        days: Annotated[int, Field(default=30, ge=1, le=365)] = 30,
    ) -> BenchmarkResult:
        """Score and compare reasoning enhancement effectiveness. Actions: score (record one output), compare (baseline vs enhanced with Cohen's d), report (full metrics). Use to PROVE if enhancement helps. Score both variants with same eval_name.

        Cohen's d: <0.2=negligible, 0.2-0.5=small, 0.5-0.8=medium, >0.8=large.
        """
        if action == "score":
            if not output.strip():
                return BenchmarkResult(
                    action="score", eval_name=eval_name, interpretation="Output required for scoring."
                )
            quality = score_output_quality(
                output,
                validation_passed=validation_passed,
                tool_calls=tool_calls,
                evidence_sources=evidence_sources,
                confidence=confidence,
            )
            store.record_eval(eval_name, variant, prompt, output, quality["total_score"], quality)
            store.record_metric(f"benchmark_{eval_name}_{variant}_score", quality["total_score"])
            return BenchmarkResult(
                action="score",
                eval_name=eval_name,
                data={"variant": variant, "score": quality["total_score"], "dimensions": quality["raw_dimensions"]},
                interpretation=f"Scored {quality['total_score']:.4f} ({variant}). Record more, then compare.",
            )

        elif action == "compare":
            comparison_data = store.get_eval_comparison(eval_name, days=days)
            cutoff = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() - days * 86400))
            baseline_scores, enhanced_scores = [], []
            with store._conn() as conn:
                rows = conn.execute(
                    "SELECT variant, score FROM eval_results WHERE eval_name=? AND created_at > ?", (eval_name, cutoff)
                ).fetchall()
                for r in rows:
                    if r[0] == "baseline":
                        baseline_scores.append(r[1])
                    elif r[0] == "enhanced":
                        enhanced_scores.append(r[1])
            stats = compare_variants(baseline_scores, enhanced_scores)
            return BenchmarkResult(
                action="compare",
                eval_name=eval_name,
                data=comparison_data,
                comparison=stats,
                interpretation=stats.get("interpretation", "Insufficient data."),
            )

        elif action == "report":
            comparison_data = store.get_eval_comparison(eval_name, days=days)
            quality_trend = store.get_quality_trend(days=days)
            calibration = store.get_calibration_score(days=days)
            report = {
                "eval_name": eval_name,
                "period_days": days,
                "comparison": comparison_data,
                "quality_trend": quality_trend,
                "calibration": calibration,
            }
            return BenchmarkResult(
                action="report",
                eval_name=eval_name,
                data=report,
                interpretation=f"Report for '{eval_name}' over {days} days.",
            )

        return BenchmarkResult(
            action=action, eval_name=eval_name, interpretation=f"Unknown: {action}. Use score, compare, or report."
        )
