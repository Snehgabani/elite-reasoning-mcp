"""Lightweight local outcome evaluation runner for Elite Reasoning MCP.

This module intentionally does not call external models. It gives the MCP an
offline smoke suite and deterministic scoring functions so teams can measure
whether reasoning scaffolds improve outcomes instead of merely adding process.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

from core.eval.research_benchmarks import ELITE_SCORECARD

_DIMENSION_NAMES = tuple(dimension.name for dimension in ELITE_SCORECARD)
_DIMENSION_WEIGHTS = {dimension.name: dimension.weight for dimension in ELITE_SCORECARD}


@dataclass(frozen=True)
class EvalFixture:
    """One local deterministic eval case."""

    name: str
    prompt: str
    candidate_output: str
    validation_passed: bool | None = None
    tool_calls: int = 0
    evidence_sources: int = 0
    confidence: float | None = None
    outcome_correct: bool | None = None
    expected_min_score: float = 0.0


@dataclass(frozen=True)
class CandidateScore:
    """Weighted score for one candidate response."""

    prompt: str
    total_score: float
    dimension_scores: dict[str, float]
    weighted_scores: dict[str, float]
    passed: bool
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EvalSuiteReport:
    """Aggregate report for a local eval suite."""

    scope: str
    aggregate_score: float
    passed: bool
    cases: tuple[dict[str, object], ...]
    scorecard_dimensions: tuple[str, ...]
    guidance: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


SMOKE_FIXTURES: tuple[EvalFixture, ...] = (
    EvalFixture(
        name="coding_agent_validation",
        prompt="Implement a focused MCP tool upgrade, expose it, and validate with tests and lint.",
        candidate_output=(
            "Implemented focused modules and MCP wrappers, preserved existing behavior, ran pytest and ruff, "
            "confirmed validation passed, and noted the installed smoke check. Risks and fallback steps were documented."
        ),
        validation_passed=True,
        tool_calls=7,
        evidence_sources=1,
        confidence=0.86,
        outcome_correct=True,
        expected_min_score=0.78,
    ),
    EvalFixture(
        name="evidence_grounded_research",
        prompt="Recommend research-backed benchmarks for agent quality and ROI.",
        candidate_output=(
            "Mapped and recommended claims against SWE-bench, ToolBench, API-Bank, HELM, FEVER, TruthfulQA, "
            "and Brier calibration. Separated evidence from assumptions, cited benchmark metrics, proposed held-out "
            "regression evals, checked contradictions, calibrated confidence, documented fallback paths, and avoided "
            "unsupported SOTA claims."
        ),
        validation_passed=None,
        tool_calls=4,
        evidence_sources=6,
        confidence=0.78,
        outcome_correct=True,
        expected_min_score=0.70,
    ),
    EvalFixture(
        name="robust_mcp_installation",
        prompt="Configure an MCP so it works reliably after restart and sync remains safe.",
        candidate_output=(
            "Verified active client capabilities, kept sync fail-closed, documented required API key or local dev opt-in, "
            "ran installed import smoke tests, and stated restart as a stop condition. Included fallback if the tool is not exposed."
        ),
        validation_passed=True,
        tool_calls=5,
        evidence_sources=2,
        confidence=0.82,
        outcome_correct=True,
        expected_min_score=0.76,
    ),
)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def _keyword_ratio(text: str, terms: tuple[str, ...], cap: int) -> float:
    matches = sum(1 for term in terms if term in text.lower())
    return min(matches / cap, 1.0)


def _clamp_score(score: float) -> float:
    return round(max(0.0, min(score, 1.0)), 3)


def _brier_quality(confidence: float, outcome_correct: bool) -> float:
    probability = max(0.0, min(confidence, 1.0))
    outcome = 1.0 if outcome_correct else 0.0
    brier = (probability - outcome) ** 2
    return _clamp_score(1.0 - brier)


def evaluate_candidate_output(
    candidate_output: str,
    prompt: str = "",
    *,
    validation_passed: bool | None = None,
    tool_calls: int = 0,
    evidence_sources: int = 0,
    confidence: float | None = None,
    outcome_correct: bool | None = None,
) -> CandidateScore:
    """Score a candidate response using deterministic signals and scorecard weights."""
    output = candidate_output.strip()
    combined = f"{prompt}\n{output}"
    notes: list[str] = []

    if validation_passed is True:
        task_success = 1.0
        notes.append("Executable validation passed.")
    elif validation_passed is False:
        task_success = 0.35
        notes.append("Executable validation failed or was not satisfied.")
    else:
        task_success = 0.45 + 0.35 * _keyword_ratio(
            output,
            ("implemented", "fixed", "completed", "solved", "configured", "mapped", "recommended", "analyzed"),
            2,
        )
        if _contains_any(output, ("blocker", "cannot verify", "not validated")):
            task_success -= 0.15
            notes.append("Task success reduced because validation/blockers remain explicit.")

    regression_prevention = 0.25 + 0.75 * _keyword_ratio(
        combined,
        ("test", "pytest", "ruff", "lint", "regression", "validation", "smoke", "passed", "eval", "held-out"),
        4,
    )
    if validation_passed is False:
        regression_prevention *= 0.6

    if tool_calls <= 0:
        tool_efficiency = 0.65 if _contains_any(output, ("direct", "minimal", "focused")) else 0.45
    elif tool_calls <= 8:
        tool_efficiency = 1.0 - max(tool_calls - 3, 0) * 0.06
    else:
        tool_efficiency = max(0.25, 0.7 - (tool_calls - 8) * 0.05)
    if _contains_any(output, ("unnecessary", "tool theater", "roi", "budget")):
        tool_efficiency = min(1.0, tool_efficiency + 0.08)

    evidence_quality = min(1.0, evidence_sources / 5)
    evidence_quality = max(
        evidence_quality,
        0.2
        + 0.8
        * _keyword_ratio(
            combined,
            ("evidence", "citation", "benchmark", "source", "fever", "truthfulqa", "swe-bench", "brier"),
            4,
        ),
    )
    if _contains_any(output, ("unsupported", "assumption", "uncertainty", "stale")):
        evidence_quality = min(1.0, evidence_quality + 0.08)

    if confidence is not None and outcome_correct is not None:
        calibration = _brier_quality(confidence, outcome_correct)
        notes.append("Calibration scored from supplied confidence/outcome pair.")
    else:
        calibration = 0.35 + 0.65 * _keyword_ratio(output, ("confidence", "uncertain", "assumption", "calibrat"), 2)

    latency_cost_roi = 0.35 + 0.65 * _keyword_ratio(
        combined,
        ("roi", "minimal", "focused", "budget", "cost", "latency", "smallest", "optional"),
        3,
    )
    if tool_calls > 12:
        latency_cost_roi *= 0.65
        notes.append("ROI reduced because tool call count is high.")

    robustness = 0.25 + 0.75 * _keyword_ratio(
        combined,
        ("fallback", "risk", "edge", "missing", "restart", "safe", "fail-closed", "blocker"),
        4,
    )

    dimension_scores = {
        "task_success": _clamp_score(task_success),
        "regression_prevention": _clamp_score(regression_prevention),
        "tool_efficiency": _clamp_score(tool_efficiency),
        "evidence_quality": _clamp_score(evidence_quality),
        "calibration": _clamp_score(calibration),
        "latency_cost_roi": _clamp_score(latency_cost_roi),
        "robustness": _clamp_score(robustness),
    }
    weighted_scores = {
        name: _clamp_score(dimension_scores[name] * _DIMENSION_WEIGHTS[name]) for name in _DIMENSION_NAMES
    }
    total = round(sum(weighted_scores.values()), 3)
    passed = total >= 0.70 and dimension_scores["task_success"] >= 0.65
    if not notes:
        notes.append("Scored from deterministic text and metadata signals.")

    return CandidateScore(
        prompt=prompt,
        total_score=total,
        dimension_scores=dimension_scores,
        weighted_scores=weighted_scores,
        passed=passed,
        notes=tuple(notes),
    )


def run_elite_eval_suite(scope: str = "smoke") -> dict[str, object]:
    """Run a local deterministic eval suite and return a JSON-compatible report."""
    normalized_scope = (scope or "smoke").strip().lower()
    fixtures = SMOKE_FIXTURES if normalized_scope == "smoke" else SMOKE_FIXTURES
    cases: list[dict[str, object]] = []
    for fixture in fixtures:
        score = evaluate_candidate_output(
            fixture.candidate_output,
            fixture.prompt,
            validation_passed=fixture.validation_passed,
            tool_calls=fixture.tool_calls,
            evidence_sources=fixture.evidence_sources,
            confidence=fixture.confidence,
            outcome_correct=fixture.outcome_correct,
        )
        case = score.to_dict()
        case["name"] = fixture.name
        case["expected_min_score"] = fixture.expected_min_score
        case["meets_expected_min_score"] = score.total_score >= fixture.expected_min_score
        cases.append(case)

    aggregate = round(sum(float(case["total_score"]) for case in cases) / len(cases), 3)
    report = EvalSuiteReport(
        scope=normalized_scope,
        aggregate_score=aggregate,
        passed=aggregate >= 0.74 and all(bool(case["meets_expected_min_score"]) for case in cases),
        cases=tuple(cases),
        scorecard_dimensions=_DIMENSION_NAMES,
        guidance=(
            "Use this smoke suite as a cheap regression guard; it is not a replacement for executable task benchmarks.",
            "For real model comparisons, run MCP-on/MCP-off candidates through the same prompts and compare weighted deltas.",
            "Prioritize task_success and regression_prevention over process volume.",
        ),
    )
    return report.to_dict()


def _json_block(data: dict[str, object]) -> str:
    return "```json\n" + json.dumps(data, indent=2, sort_keys=True) + "\n```"


def elite_eval_suite_markdown(scope: str = "smoke") -> str:
    """Render the local eval suite report as Markdown plus JSON."""
    report = run_elite_eval_suite(scope)
    lines = [
        "# Elite Local Eval Suite",
        "",
        f"**Scope:** `{report['scope']}`",
        f"**Aggregate score:** {report['aggregate_score']}",
        f"**Passed:** {report['passed']}",
        "",
        "## Scorecard Dimensions",
    ]
    lines.extend(f"- `{name}`" for name in report["scorecard_dimensions"])
    lines.extend(["", "## Cases"])
    for case in report["cases"]:
        lines.extend(
            [
                f"### {case['name']}",
                f"- Total score: {case['total_score']}",
                f"- Passed: {case['passed']}",
                f"- Expected minimum: {case['expected_min_score']}",
                f"- Meets expected minimum: {case['meets_expected_min_score']}",
            ]
        )
        dimension_summary = ", ".join(
            f"{name}={score}" for name, score in sorted(dict(case["dimension_scores"]).items())
        )
        lines.append(f"- Dimensions: {dimension_summary}")
    lines.extend(["", "## Guidance"])
    lines.extend(f"- {item}" for item in report["guidance"])
    lines.extend(["", "## JSON", _json_block(report)])
    return "\n".join(lines)


def extract_json_from_markdown(markdown: str) -> dict[str, object]:
    """Small test helper for round-tripping rendered reports."""
    match = re.search(r"```json\n(.*?)\n```", markdown, flags=re.DOTALL)
    if not match:
        return {}
    parsed = json.loads(match.group(1))
    return parsed if isinstance(parsed, dict) else {}
