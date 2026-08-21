"""Bias Scan Tool — Detect cognitive biases, sycophancy, and red flags.

Research: SYCON-Bench (EMNLP 2025), CAU SM (ICLR 2025),
Kamruzzaman & Kim (RANLP 2025).
"""

from __future__ import annotations

import time
from typing import Annotated, Any

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from core.cognitive.loop.core.store import SingularityStore
from core.cognitive.loop.pipeline.bias_scanner import run_bias_scan

_BIAS_ANNOTATIONS = ToolAnnotations(
    title="Scan for cognitive biases",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


class BiasScanResult(BaseModel):
    red_flags: list[dict[str, Any]]
    sycophancy_score: float
    confidence_evidence_gap: float
    overall_risk: str
    recommendations: list[str]
    anti_sycophancy_prompt: str


def register(mcp, store: SingularityStore):
    """Register the bias_scan tool."""

    @mcp.tool(name="bias_scan", annotations=_BIAS_ANNOTATIONS)
    def bias_scan(
        text: Annotated[str, Field(min_length=10, max_length=8000)],
        user_prompt: Annotated[str, Field(default="", max_length=4000)] = "",
        confidence: Annotated[float, Field(default=0.7, ge=0.0, le=1.0)] = 0.7,
    ) -> BiasScanResult:
        """Scan text for cognitive biases, sycophancy, and red flags. Returns flagged issues and fixes. Use after reasoning_run for important outputs. Skip for trivial text.

        Detects 10 cognitive biases (anchoring, confirmation, sunk cost, etc.),
        sycophancy (agreeing without analysis), and confidence-evidence gaps.
        """
        start = time.time()
        result = run_bias_scan(text, user_prompt, confidence)

        store.log_tool_usage(
            "bias_scan",
            f"risk={result.overall_risk}",
            "",
            getattr(mcp, "_session_id", ""),
            int((time.time() - start) * 1000),
        )
        store.record_metric(
            "bias_scan_risk", {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(result.overall_risk, 0)
        )

        return BiasScanResult(
            red_flags=[
                {
                    "type": f.bias_type,
                    "severity": f.severity,
                    "description": f.description,
                    "evidence": f.evidence,
                    "fix": f.recommendation,
                }
                for f in result.red_flags
            ],
            sycophancy_score=result.sycophancy_score,
            confidence_evidence_gap=result.confidence_evidence_gap,
            overall_risk=result.overall_risk,
            recommendations=result.recommendations,
            anti_sycophancy_prompt=result.anti_sycophancy_prompt,
        )
