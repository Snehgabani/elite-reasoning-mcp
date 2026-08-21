"""Metrics collection, scoring, and diagnostic reporting.

Provides the quantitative backbone for measuring whether reasoning
enhancements actually improve LLM outcomes. Every tool call, session,
and eval result flows through here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionMetrics:
    """Metrics collected during a single reasoning session."""

    session_id: str
    prompt: str
    intent: str
    complexity: int
    budget_tier: str
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    duration_ms: int = 0
    tool_calls: int = 0
    reasoning_steps: int = 0
    evidence_sources: int = 0
    anti_patterns_hit: int = 0
    memory_items_used: int = 0
    confidence: float = 0.0
    outcome_score: float = 0.0
    validation_passed: bool | None = None
    notes: list[str] = field(default_factory=list)

    def finish(self):
        self.end_time = time.time()
        self.duration_ms = int((self.end_time - self.start_time) * 1000)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "prompt": self.prompt[:200],
            "intent": self.intent,
            "complexity": self.complexity,
            "budget_tier": self.budget_tier,
            "duration_ms": self.duration_ms,
            "tool_calls": self.tool_calls,
            "reasoning_steps": self.reasoning_steps,
            "evidence_sources": self.evidence_sources,
            "anti_patterns_hit": self.anti_patterns_hit,
            "memory_items_used": self.memory_items_used,
            "confidence": self.confidence,
            "outcome_score": self.outcome_score,
            "validation_passed": self.validation_passed,
            "notes": self.notes,
        }


# ── Scorecard Dimensions (Research-Backed) ──────────────────

SCORECARD_DIMENSIONS = {
    "task_success": {
        "weight": 0.30,
        "description": "Did the output solve the task? Executable validation or accepted outcome.",
        "benchmarks": ["SWE-bench Verified", "AgentBench"],
    },
    "regression_prevention": {
        "weight": 0.18,
        "description": "Were past mistakes avoided? Tests passing, no repeated errors.",
        "benchmarks": ["SWE-bench Verified"],
    },
    "tool_efficiency": {
        "weight": 0.14,
        "description": "Right tools used? Useful calls / total calls.",
        "benchmarks": ["API-Bank", "ToolBench"],
    },
    "evidence_quality": {
        "weight": 0.14,
        "description": "Claims backed by evidence? Citations, sources, grounding.",
        "benchmarks": ["FEVER", "TruthfulQA"],
    },
    "calibration": {
        "weight": 0.10,
        "description": "Confidence matches reality? Brier score, overconfidence rate.",
        "benchmarks": ["Brier Score"],
    },
    "latency_roi": {
        "weight": 0.08,
        "description": "Quality gain justifies added time? Score/ms ratio.",
        "benchmarks": ["HELM"],
    },
    "robustness": {
        "weight": 0.06,
        "description": "Handles edge cases, failures, missing tools gracefully?",
        "benchmarks": ["AgentBench", "HELM"],
    },
}


def compute_weighted_score(dimension_scores: dict[str, float]) -> dict[str, Any]:
    """Compute the weighted Elite score from individual dimension scores (0-1)."""
    weighted = {}
    total = 0.0
    for name, config in SCORECARD_DIMENSIONS.items():
        raw = dimension_scores.get(name, 0.5)
        weighted[name] = round(raw * config["weight"], 4)
        total += weighted[name]
    return {
        "total_score": round(total, 4),
        "weighted_dimensions": weighted,
        "raw_dimensions": {k: round(v, 4) for k, v in dimension_scores.items()},
        "passed": total >= 0.70 and dimension_scores.get("task_success", 0) >= 0.65,
    }


def score_output_quality(
    output: str,
    *,
    validation_passed: bool | None = None,
    tool_calls: int = 0,
    evidence_sources: int = 0,
    confidence: float | None = None,
    outcome_correct: bool | None = None,
) -> dict[str, Any]:
    """Score a candidate output using deterministic signals and scorecard weights.

    This is the core scoring function that evaluates whether reasoning
    enhancements actually improved output quality.
    """
    text = output.strip()
    lower = text.lower()

    # 1. Task Success (0-1)
    if validation_passed is True:
        task_success = 1.0
    elif validation_passed is False:
        task_success = 0.35
    else:
        completion_signals = _keyword_ratio(
            lower,
            (
                "implemented",
                "fixed",
                "completed",
                "solved",
                "configured",
                "mapped",
                "recommended",
                "analyzed",
                "created",
                "built",
                "identified",
                "evaluated",
                "assessed",
                "compared",
                "designed",
                "proposed",
                "researched",
                "investigated",
                "documented",
                "verified",
                "includes",
                "provides",
                "covering",
                "tracking",
                "calibration",
            ),
            5,
        )
        blocker_penalty = 0.15 if _contains_any(lower, ("blocker", "cannot verify", "not validated", "failed")) else 0
        task_success = max(0, 0.45 + 0.40 * completion_signals - blocker_penalty)

    # 2. Regression Prevention (0-1)
    regression = 0.25 + 0.75 * _keyword_ratio(
        lower,
        ("test", "pytest", "lint", "regression", "validation", "smoke", "passed", "eval", "held-out", "no regressions"),
        4,
    )
    if validation_passed is False:
        regression *= 0.6

    # 3. Tool Efficiency (0-1)
    if tool_calls <= 0:
        tool_eff = 0.65 if _contains_any(lower, ("direct", "minimal", "focused")) else 0.50
    elif tool_calls <= 3:
        tool_eff = 0.95
    elif tool_calls <= 8:
        tool_eff = 1.0 - (tool_calls - 3) * 0.06
    else:
        tool_eff = max(0.25, 0.70 - (tool_calls - 8) * 0.05)

    # 4. Evidence Quality (0-1)
    evidence = min(1.0, evidence_sources / 5)
    evidence = max(
        evidence,
        0.20
        + 0.80
        * _keyword_ratio(
            lower, ("evidence", "citation", "benchmark", "source", "research", "paper", "documentation", "reference"), 4
        ),
    )
    if _contains_any(lower, ("unsupported", "assumption", "uncertainty")):
        evidence = min(1.0, evidence + 0.05)

    # 5. Calibration (0-1)
    if confidence is not None and outcome_correct is not None:
        brier = (max(0, min(confidence, 1.0)) - (1.0 if outcome_correct else 0.0)) ** 2
        calibration = max(0, 1.0 - brier)
    else:
        calibration = 0.35 + 0.65 * _keyword_ratio(
            lower, ("confidence", "uncertain", "assumption", "calibrat", "probability"), 2
        )

    # 6. Latency ROI (0-1)
    latency_roi = 0.35 + 0.65 * _keyword_ratio(
        lower, ("roi", "minimal", "focused", "budget", "cost", "efficient", "optimal"), 3
    )
    if tool_calls > 12:
        latency_roi *= 0.65

    # 7. Robustness (0-1)
    robustness = 0.25 + 0.75 * _keyword_ratio(
        lower,
        (
            "fallback",
            "risk",
            "edge case",
            "missing",
            "error handling",
            "safe",
            "fail-closed",
            "graceful",
            "retry",
            "verified",
            "validated",
            "checked",
            "confirmed",
            "tested",
            "no other",
        ),
        4,
    )

    dimensions = {
        "task_success": _clamp(task_success),
        "regression_prevention": _clamp(regression),
        "tool_efficiency": _clamp(tool_eff),
        "evidence_quality": _clamp(evidence),
        "calibration": _clamp(calibration),
        "latency_roi": _clamp(latency_roi),
        "robustness": _clamp(robustness),
    }

    result = compute_weighted_score(dimensions)
    result["notes"] = []
    if validation_passed is False:
        result["notes"].append("Validation failed — task_success penalized.")
    if tool_calls > 10:
        result["notes"].append(f"High tool count ({tool_calls}) — efficiency reduced.")
    if evidence_sources == 0:
        result["notes"].append("No evidence sources cited.")

    return result


# ── A/B Comparison Engine ───────────────────────────────────


def compare_variants(baseline_scores: list[float], enhanced_scores: list[float]) -> dict[str, Any]:
    """Compare baseline vs enhanced variant scores statistically."""
    if not baseline_scores or not enhanced_scores:
        return {
            "comparison": "insufficient_data",
            "baseline_n": len(baseline_scores),
            "enhanced_n": len(enhanced_scores),
        }

    b_mean = sum(baseline_scores) / len(baseline_scores)
    e_mean = sum(enhanced_scores) / len(enhanced_scores)
    delta = e_mean - b_mean

    # Effect size (Cohen's d approximation)
    b_std = _stddev(baseline_scores) if len(baseline_scores) > 1 else 0.1
    e_std = _stddev(enhanced_scores) if len(enhanced_scores) > 1 else 0.1
    pooled_std = ((b_std**2 + e_std**2) / 2) ** 0.5 or 0.1
    cohens_d = delta / pooled_std

    # Win rate: % of enhanced scores above baseline mean
    win_rate = sum(1 for s in enhanced_scores if s > b_mean) / len(enhanced_scores)

    if abs(cohens_d) < 0.2:
        significance = "negligible"
    elif abs(cohens_d) < 0.5:
        significance = "small"
    elif abs(cohens_d) < 0.8:
        significance = "medium"
    else:
        significance = "large"

    return {
        "comparison": f"enhanced_{'better' if delta > 0 else 'worse'}",
        "delta": round(delta, 4),
        "baseline_mean": round(b_mean, 4),
        "enhanced_mean": round(e_mean, 4),
        "cohens_d": round(cohens_d, 4),
        "effect_size": significance,
        "win_rate": round(win_rate, 4),
        "baseline_n": len(baseline_scores),
        "enhanced_n": len(enhanced_scores),
        "baseline_std": round(b_std, 4),
        "enhanced_std": round(e_std, 4),
        "interpretation": _interpret_effect(cohens_d, significance, delta),
    }


# ── Helpers ─────────────────────────────────────────────────


def _keyword_ratio(text: str, terms: tuple[str, ...], cap: int) -> float:
    matches = sum(1 for t in terms if t in text)
    return min(matches / cap, 1.0)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(t in text for t in terms)


def _clamp(v: float) -> float:
    return round(max(0.0, min(1.0, v)), 4)


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((v - mean) ** 2 for v in values) / (len(values) - 1)) ** 0.5


def _interpret_effect(cohens_d: float, significance: str, delta: float) -> str:
    direction = "improvement" if delta > 0 else "regression"
    if significance == "negligible":
        return f"Negligible difference ({delta:+.4f}). Reasoning enhancement shows no measurable impact."
    elif significance == "small":
        return f"Small {direction} (d={cohens_d:.2f}). Marginal benefit — consider if added latency is justified."
    elif significance == "medium":
        return (
            f"Medium {direction} (d={cohens_d:.2f}). Meaningful change — reasoning enhancement has measurable impact."
        )
    else:
        return f"Large {direction} (d={cohens_d:.2f}). Significant impact — reasoning enhancement substantially {'helps' if delta > 0 else 'hurts'}."
