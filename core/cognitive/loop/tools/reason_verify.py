"""Reasoning Verification Tool — Evidence-gated completion checking.

Verifies that a task has been completed with proper evidence before
allowing the agent to claim success. Checks:
1. All required validation gates passed
2. Evidence is attached for each completed step
3. No unresolved anti-patterns
4. Quality score meets minimum threshold

Research basis: Formal verification, evidence-based software engineering,
gate-based quality assurance (Boehm, 1981).
"""

from __future__ import annotations

import json
import time
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from core.cognitive.loop.core.metrics import score_output_quality
from core.cognitive.loop.core.store import SingularityStore


class VerifyInput(BaseModel):
    session_id: Annotated[str, Field(min_length=3, max_length=128)]
    output: Annotated[str, Field(min_length=1, max_length=8000)]
    validation_passed: Annotated[bool | None, Field(default=None)]
    tool_calls: Annotated[int, Field(default=0, ge=0)]
    evidence_sources: Annotated[int, Field(default=0, ge=0)]
    confidence: Annotated[float, Field(default=0.7, ge=0.0, le=1.0)]


class GateCheck(BaseModel):
    name: str
    status: Literal["passed", "failed", "skipped", "warning"]
    detail: str


class VerifyResult(BaseModel):
    session_id: str
    overall_status: Literal["verified", "blocked", "warning"]
    quality_score: dict[str, Any]
    gates: list[GateCheck]
    anti_patterns_remaining: list[dict[str, Any]]
    recommendations: list[str]
    duration_ms: int
    metrics_recorded: bool


def register(mcp, store: SingularityStore):
    """Register the reasoning_verify tool on the MCP server."""

    @mcp.tool(name="reasoning_verify")
    def reasoning_verify(
        session_id: Annotated[str, Field(min_length=3, max_length=128)],
        output: Annotated[str, Field(min_length=1, max_length=8000)],
        validation_passed: bool | None = None,
        tool_calls: int = 0,
        evidence_sources: int = 0,
        confidence: float = 0.7,
    ) -> VerifyResult:
        """Verify that a task is complete with proper evidence.

        Runs all validation gates, scores output quality against the 7-dimension
        scorecard, checks for unresolved anti-patterns, and records metrics.
        Returns verified/blocked/warning status.

        Use this BEFORE claiming a task is complete. It tells you if you can
        ship, what's missing, and records the quality score for tracking.
        """
        start = time.time()

        # Load session
        session = store.get_session(session_id)
        if session:
            try:
                _ = json.loads(session.get("metrics_json", "{}"))
            except (json.JSONDecodeError, TypeError) as exc:
                # Malformed session metrics ignored gracefully
                _ = str(exc)

        # Run verification gates
        gates = []

        # Gate 1: Output quality
        quality = score_output_quality(
            output,
            validation_passed=validation_passed,
            tool_calls=tool_calls,
            evidence_sources=evidence_sources,
            confidence=confidence,
        )
        if quality["passed"]:
            gates.append(
                GateCheck(
                    name="quality_score",
                    status="passed",
                    detail=f"Score: {quality['total_score']:.3f} (threshold: 0.70)",
                )
            )
        else:
            gates.append(
                GateCheck(
                    name="quality_score",
                    status="failed",
                    detail=f"Score: {quality['total_score']:.3f} below threshold 0.70",
                )
            )

        # Gate 2: Task success dimension
        task_score = quality["raw_dimensions"].get("task_success", 0)
        if task_score >= 0.65:
            gates.append(
                GateCheck(
                    name="task_success", status="passed", detail=f"Task success: {task_score:.3f} (threshold: 0.65)"
                )
            )
        else:
            gates.append(
                GateCheck(
                    name="task_success", status="failed", detail=f"Task success: {task_score:.3f} below threshold 0.65"
                )
            )

        # Gate 3: Validation status
        if validation_passed is True:
            gates.append(GateCheck(name="validation", status="passed", detail="Executable validation passed."))
        elif validation_passed is False:
            gates.append(GateCheck(name="validation", status="failed", detail="Executable validation FAILED."))
        else:
            gates.append(
                GateCheck(
                    name="validation", status="warning", detail="Validation not run — manual verification needed."
                )
            )

        # Gate 4: Evidence grounding
        if evidence_sources >= 2:
            gates.append(
                GateCheck(name="evidence", status="passed", detail=f"{evidence_sources} evidence sources cited.")
            )
        elif evidence_sources >= 1:
            gates.append(
                GateCheck(
                    name="evidence",
                    status="warning",
                    detail=f"Only {evidence_sources} evidence source(s) — consider more.",
                )
            )
        else:
            gates.append(GateCheck(name="evidence", status="warning", detail="No evidence sources cited."))

        # Gate 5: Tool efficiency
        tool_score = quality["raw_dimensions"].get("tool_efficiency", 0)
        if tool_score >= 0.6:
            gates.append(
                GateCheck(
                    name="tool_efficiency",
                    status="passed",
                    detail=f"Tool efficiency: {tool_score:.3f} ({tool_calls} calls)",
                )
            )
        else:
            gates.append(
                GateCheck(
                    name="tool_efficiency",
                    status="warning",
                    detail=f"Tool efficiency low: {tool_score:.3f} ({tool_calls} calls — consider fewer)",
                )
            )

        # Check anti-patterns
        anti_patterns = store.check_anti_patterns(output[:500], limit=3)

        # Overall status
        failed_gates = [g for g in gates if g.status == "failed"]
        if failed_gates:
            overall_status = "blocked"
        elif any(g.status == "warning" for g in gates):
            overall_status = "warning"
        else:
            overall_status = "verified"

        # Recommendations
        recommendations = []
        if overall_status == "blocked":
            recommendations.append(f"BLOCKED: {len(failed_gates)} gate(s) failed. Fix before claiming completion.")
            for g in failed_gates:
                recommendations.append(f"  - {g.name}: {g.detail}")
        if anti_patterns:
            recommendations.append(f"Review {len(anti_patterns)} related past mistake(s) before delivering.")
        if evidence_sources == 0:
            recommendations.append("Add evidence sources to strengthen the output.")
        if confidence < 0.6:
            recommendations.append("Confidence is low — consider using reasoning_amplify before delivering.")

        # Record metrics
        duration_ms = int((time.time() - start) * 1000)
        metrics_recorded = False
        try:
            # Update session
            outcome = {
                "status": overall_status,
                "quality_score": quality["total_score"],
                "gates_passed": len([g for g in gates if g.status == "passed"]),
                "gates_failed": len(failed_gates),
            }
            metrics = {
                "tool_calls": tool_calls,
                "evidence_sources": evidence_sources,
                "confidence": confidence,
                "quality_dimensions": quality["raw_dimensions"],
            }
            store.complete_session(session_id, outcome, metrics, duration_ms)

            # Record quality score
            store.record_quality_score(
                score=int(quality["total_score"] * 100),
                dimension="verification",
                notes=f"Status: {overall_status} | Gates: {len(gates)} | Session: {session_id}",
            )

            # Record metric snapshots
            store.record_metric("verify_quality_score", quality["total_score"])
            store.record_metric("verify_duration_ms", duration_ms, "ms")
            store.record_metric("verify_tool_calls", tool_calls)

            metrics_recorded = True
        except Exception as exc:
            # Explicit non-fatal exception suppression
            _ = str(exc)

        store.log_tool_usage(
            "reasoning_verify",
            session_id[:50],
            json.dumps({"status": overall_status, "score": quality["total_score"]}),
            session_id,
            duration_ms,
        )

        return VerifyResult(
            session_id=session_id,
            overall_status=overall_status,
            quality_score=quality,
            gates=gates,
            anti_patterns_remaining=anti_patterns,
            recommendations=recommendations,
            duration_ms=duration_ms,
            metrics_recorded=metrics_recorded,
        )
