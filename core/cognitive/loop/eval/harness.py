"""Local Evaluation Harness — Smoke benchmarks that measure reasoning quality.

Runs deterministic evaluation cases to verify the scoring system works
correctly and provides a baseline for A/B comparisons.

This is NOT an LLM eval — it tests the scoring infrastructure itself.
For real model comparisons, use benchmark_run with actual model outputs.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from core.cognitive.loop.core.metrics import SCORECARD_DIMENSIONS, score_output_quality
from core.cognitive.loop.core.store import SingularityStore


@dataclass(frozen=True)
class SmokeFixture:
    """A deterministic evaluation fixture."""
    name: str
    prompt: str
    candidate_output: str
    validation_passed: bool | None
    tool_calls: int
    evidence_sources: int
    confidence: float | None
    outcome_correct: bool | None
    expected_min_score: float


# ── Smoke Test Fixtures ─────────────────────────────────────

SMOKE_FIXTURES: tuple[SmokeFixture, ...] = (
    SmokeFixture(
        name="high_quality_implementation",
        prompt="Implement a focused API endpoint with validation, error handling, and tests.",
        candidate_output=(
            "Implemented the /api/users endpoint with Pydantic validation, proper error responses "
            "(400/404/500), database transaction handling, and 12 unit tests covering happy path, "
            "validation errors, and edge cases. All tests pass. Lint clean. Added rate limiting "
            "middleware and documented the API contract. Confidence: 0.92 based on test coverage "
            "and code review."
        ),
        validation_passed=True,
        tool_calls=5,
        evidence_sources=3,
        confidence=0.92,
        outcome_correct=True,
        expected_min_score=0.78,
    ),
    SmokeFixture(
        name="research_grounded_analysis",
        prompt="Recommend research-backed benchmarks for evaluating coding agents.",
        candidate_output=(
            "Based on current research, the recommended benchmark suite for coding agents includes: "
            "SWE-bench Verified for real-world GitHub issue resolution (Jimenez et al., 2024), "
            "HumanEval for function-level synthesis (Chen et al., 2021), ToolBench for multi-step "
            "tool use (Qin et al., 2023), and AgentBench for long-horizon decisions (Liu et al., 2024). "
            "For calibration, Brier score tracking provides quantitative confidence measurement. "
            "Evidence from 6 peer-reviewed sources. Confidence: 0.85 based on citation coverage."
        ),
        validation_passed=None,
        tool_calls=4,
        evidence_sources=6,
        confidence=0.85,
        outcome_correct=True,
        expected_min_score=0.72,
    ),
    SmokeFixture(
        name="minimal_correct_fix",
        prompt="Fix the typo in the variable name.",
        candidate_output="Fixed: renamed 'recieve' to 'receive' on line 42. Verified with grep that no other instances exist.",
        validation_passed=True,
        tool_calls=1,
        evidence_sources=0,
        confidence=0.95,
        outcome_correct=True,
        expected_min_score=0.65,
    ),
    SmokeFixture(
        name="low_quality_output",
        prompt="Implement a secure authentication system with OAuth2.",
        candidate_output=(
            "I wrote some code for auth. It should work. I used a library I found. "
            "Not sure about the security implications but it compiles."
        ),
        validation_passed=False,
        tool_calls=2,
        evidence_sources=0,
        confidence=0.4,
        outcome_correct=False,
        expected_min_score=0.0,  # This should fail
    ),
    SmokeFixture(
        name="over_engineered_solution",
        prompt="Add a simple logging statement to track API calls.",
        candidate_output=(
            "Implemented a comprehensive logging framework with 15 middleware layers, "
            "custom log aggregation pipeline, distributed tracing with OpenTelemetry, "
            "log rotation with S3 archival, and a Grafana dashboard. Used 45 tool calls "
            "across 8 files. The simple logging statement is included somewhere in there."
        ),
        validation_passed=True,
        tool_calls=45,
        evidence_sources=0,
        confidence=0.6,
        outcome_correct=True,
        expected_min_score=0.0,  # Efficiency penalty should drag this down
    ),
)


def run_smoke_benchmark(brain_dir: str) -> dict:
    """Run the smoke benchmark suite and return a detailed report."""
    store = SingularityStore(brain_dir)
    cases = []
    all_passed = True

    for fixture in SMOKE_FIXTURES:
        score = score_output_quality(
            fixture.candidate_output,
            validation_passed=fixture.validation_passed,
            tool_calls=fixture.tool_calls,
            evidence_sources=fixture.evidence_sources,
            confidence=fixture.confidence,
            outcome_correct=fixture.outcome_correct,
        )

        meets_threshold = score["total_score"] >= fixture.expected_min_score
        if not meets_threshold and fixture.expected_min_score > 0:
            all_passed = False

        case_result = {
            "name": fixture.name,
            "total_score": score["total_score"],
            "dimensions": score["raw_dimensions"],
            "passed": score["passed"],
            "meets_threshold": meets_threshold,
            "expected_min": fixture.expected_min_score,
            "delta_from_expected": round(score["total_score"] - fixture.expected_min_score, 4),
            "notes": score.get("notes", []),
        }
        cases.append(case_result)

        # Record in store for tracking
        store.record_eval(
            eval_name="smoke",
            variant="enhanced",
            prompt=fixture.prompt,
            output=fixture.candidate_output,
            score=score["total_score"],
            metrics=score,
        )

    # Aggregate results
    scores = [c["total_score"] for c in cases]
    aggregate = round(sum(scores) / len(scores), 4) if scores else 0.0

    # Dimension averages
    dim_avgs = {}
    for dim in SCORECARD_DIMENSIONS:
        vals = [c["dimensions"].get(dim, 0) for c in cases]
        dim_avgs[dim] = round(sum(vals) / len(vals), 4) if vals else 0.0

    report = {
        "suite": "smoke",
        "version": "3.0.0",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "aggregate_score": aggregate,
        "passed": all_passed,
        "cases": cases,
        "dimension_averages": dim_avgs,
        "thresholds": {
            "aggregate_min": 0.65,
            "individual_min": "per-fixture expected_min_score",
            "task_success_min": 0.65,
        },
        "interpretation": _interpret_results(aggregate, all_passed, dim_avgs),
    }

    # Record metric
    store.record_metric("smoke_aggregate_score", aggregate)

    return report


def _interpret_results(aggregate: float, all_passed: bool, dim_avgs: dict) -> str:
    """Generate human-readable interpretation of results."""
    lines = []
    if all_passed and aggregate >= 0.70:
        lines.append(f"✅ All fixtures passed. Aggregate score: {aggregate:.4f} (good).")
    elif all_passed:
        lines.append(f"⚠️ All fixtures passed but aggregate is borderline: {aggregate:.4f}.")
    else:
        lines.append(f"❌ Some fixtures failed. Aggregate: {aggregate:.4f}. Review scoring thresholds.")

    # Check weakest dimensions
    weakest = min(dim_avgs, key=dim_avgs.get) if dim_avgs else "unknown"
    strongest = max(dim_avgs, key=dim_avgs.get) if dim_avgs else "unknown"
    lines.append(f"Weakest dimension: {weakest} ({dim_avgs.get(weakest, 0):.4f})")
    lines.append(f"Strongest dimension: {strongest} ({dim_avgs.get(strongest, 0):.4f})")

    return " ".join(lines)
