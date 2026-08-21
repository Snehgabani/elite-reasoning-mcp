"""Domain-Specific Scoring Rubrics — Structured evaluation criteria.

Each rubric defines explicit scoring criteria for a domain, so that
output quality can be measured consistently. Rubrics are based on
software engineering best practices and research evaluation frameworks.

Research basis: Rubric-based evaluation (Brookhart, 2013),
HELM multi-metric evaluation (Liang et al., 2023).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RubricCriterion:
    """One criterion in a scoring rubric."""
    name: str
    weight: float
    excellent: str  # Score 0.9-1.0
    adequate: str   # Score 0.6-0.89
    poor: str       # Score 0.0-0.59


@dataclass(frozen=True)
class DomainRubric:
    """Complete scoring rubric for a domain."""
    domain: str
    description: str
    criteria: tuple[RubricCriterion, ...]
    total_weight: float = 1.0
    source: str = ""


# ── Code Implementation Rubric ───────────────────────────────

CODE_RUBRIC = DomainRubric(
    domain="code_implementation",
    description="Evaluate code implementation quality",
    criteria=(
        RubricCriterion("correctness", 0.30,
            "All requirements met. Tests pass. Edge cases handled.",
            "Core requirements met. Most tests pass.",
            "Missing requirements or failing tests."),
        RubricCriterion("design", 0.20,
            "Clean abstractions. SOLID principles. Minimal coupling.",
            "Reasonable structure. Some coupling or duplication.",
            "God objects, tight coupling, or no structure."),
        RubricCriterion("error_handling", 0.15,
            "All error paths handled. Graceful degradation. Logging.",
            "Happy path + critical errors handled.",
            "No error handling. Silent failures."),
        RubricCriterion("testing", 0.15,
            "Unit + integration tests. Edge cases covered. >80% coverage.",
            "Unit tests for main paths. Some edge cases.",
            "No tests or only smoke tests."),
        RubricCriterion("documentation", 0.10,
            "API docs, inline comments for non-obvious logic, README.",
            "Some inline comments. Function signatures clear.",
            "No documentation. Magic numbers."),
        RubricCriterion("performance", 0.10,
            "Optimal complexity. No N+1 queries. Bounded resources.",
            "Acceptable performance. Minor inefficiencies.",
            "O(n²) or unbounded resource usage."),
    ),
    source="Google Engineering Practices, Clean Code (Martin, 2008)",
)


# ── Debugging Rubric ─────────────────────────────────────────

DEBUG_RUBRIC = DomainRubric(
    domain="debugging",
    description="Evaluate debugging quality",
    criteria=(
        RubricCriterion("root_cause", 0.30,
            "True root cause identified with evidence chain. Five-whys applied.",
            "Probable cause identified with some evidence.",
            "Symptom described as cause. Guessing."),
        RubricCriterion("fix_quality", 0.25,
            "Minimal fix addressing root cause. No regressions. Tests added.",
            "Fix works but addresses symptom, not root cause.",
            "Fix introduces new issues or doesn't resolve the problem."),
        RubricCriterion("reproduction", 0.20,
            "Exact reproduction steps documented. Minimal repro case.",
            "Bug reproduced but steps not minimal.",
            "Cannot reproduce. Working from description only."),
        RubricCriterion("prevention", 0.15,
            "Regression test added. Anti-pattern recorded. Systemic fix.",
            "Test added for this specific case.",
            "No prevention measures. Will recur."),
        RubricCriterion("communication", 0.10,
            "Clear explanation of what, why, and how fixed. Impact assessed.",
            "Basic explanation of the fix.",
            "No explanation. 'Fixed it.'"),
    ),
    source="Debugging: The 9 Indispensable Rules (Butcher, 2008)",
)


# ── Architecture Decision Rubric ─────────────────────────────

ARCHITECTURE_RUBRIC = DomainRubric(
    domain="architecture_decision",
    description="Evaluate architectural decision quality",
    criteria=(
        RubricCriterion("alternatives", 0.25,
            "3+ alternatives enumerated with specific pros/cons each.",
            "2 alternatives with basic comparison.",
            "No alternatives considered. First idea adopted."),
        RubricCriterion("trade_offs", 0.25,
            "Explicit trade-off analysis. Costs quantified where possible.",
            "Trade-offs mentioned but not analyzed.",
            "No trade-off discussion. Only benefits listed."),
        RubricCriterion("rationale", 0.20,
            "Decision rationale is self-contained and future-proof.",
            "Rationale present but requires external context.",
            "No rationale. 'Because we decided.'"),
        RubricCriterion("risk_assessment", 0.15,
            "Risks enumerated with mitigation plans. Reversibility assessed.",
            "Some risks mentioned.",
            "No risk assessment."),
        RubricCriterion("constraints", 0.15,
            "All constraints (time, budget, team, tech) explicitly addressed.",
            "Key constraints mentioned.",
            "Constraints ignored."),
    ),
    source="Architecture Decision Records (Nygard, 2011)",
)


# ── Research/Analysis Rubric ─────────────────────────────────

RESEARCH_RUBRIC = DomainRubric(
    domain="research_analysis",
    description="Evaluate research and analysis quality",
    criteria=(
        RubricCriterion("evidence", 0.30,
            "5+ quality sources cited. Recency verified. Primary sources preferred.",
            "2-4 sources cited. Some secondary sources.",
            "No sources. Opinions presented as facts."),
        RubricCriterion("synthesis", 0.25,
            "Evidence mapped to specific claims. Confidence levels assigned.",
            "General synthesis without claim-evidence mapping.",
            "List of sources without synthesis."),
        RubricCriterion("contradictions", 0.20,
            "Conflicting evidence explicitly identified and resolved.",
            "Contradictions noted but not resolved.",
            "Contradictions ignored or not detected."),
        RubricCriterion("uncertainty", 0.15,
            "Uncertainty quantified. Assumptions explicit. Confidence intervals.",
            "Some uncertainty acknowledged.",
            "False certainty. No hedging."),
        RubricCriterion("actionability", 0.10,
            "Clear recommendations with implementation guidance.",
            "General recommendations.",
            "No actionable conclusions."),
    ),
    source="Systematic Literature Review (Kitchenham, 2004)",
)


# ── Deployment Rubric ────────────────────────────────────────

DEPLOY_RUBRIC = DomainRubric(
    domain="deployment",
    description="Evaluate deployment quality",
    criteria=(
        RubricCriterion("pre_checks", 0.25,
            "Before-state captured. Smoke tests pass. Rollback plan tested.",
            "Basic pre-checks done. Rollback documented.",
            "No pre-checks. Deploying blind."),
        RubricCriterion("monitoring", 0.25,
            "Key metrics monitored. Alerts configured. Dashboard available.",
            "Basic monitoring in place.",
            "No monitoring. Finding out from users."),
        RubricCriterion("rollback", 0.20,
            "Tested rollback procedure. Data migration reversible. Time-to-rollback < 5 min.",
            "Rollback procedure documented but untested.",
            "No rollback plan."),
        RubricCriterion("verification", 0.20,
            "Post-deploy smoke tests. Metrics comparison. Health checks automated.",
            "Manual verification after deploy.",
            "No verification. Assuming it works."),
        RubricCriterion("communication", 0.10,
            "Stakeholders notified. Change log updated. Incident channel ready.",
            "Team notified.",
            "No communication."),
    ),
    source="Site Reliability Engineering (Beyer et al., 2016)",
)


# ── Rubric Registry ─────────────────────────────────────────

RUBRICS: dict[str, DomainRubric] = {
    "code_implementation": CODE_RUBRIC,
    "debugging": DEBUG_RUBRIC,
    "architecture_decision": ARCHITECTURE_RUBRIC,
    "research_analysis": RESEARCH_RUBRIC,
    "deployment": DEPLOY_RUBRIC,
}

# Intent → Rubric mapping
INTENT_RUBRIC_MAP = {
    "build": "code_implementation",
    "debug": "debugging",
    "fix": "debugging",
    "decide": "architecture_decision",
    "design": "architecture_decision",
    "research": "research_analysis",
    "audit": "research_analysis",
    "deploy": "deployment",
    "optimize": "code_implementation",
    "test": "code_implementation",
}


def get_rubric_for_intent(intent: str) -> DomainRubric:
    """Get the appropriate rubric for a given intent."""
    rubric_key = INTENT_RUBRIC_MAP.get(intent, "code_implementation")
    return RUBRICS[rubric_key]


def score_with_rubric(rubric: DomainRubric, output: str, signals: dict[str, float] | None = None) -> dict:
    """Score an output against a domain rubric.
    
    Uses text signals to estimate criterion scores when no explicit
    signals are provided. Returns weighted total and per-criterion scores.
    """
    lower = output.lower()
    criterion_scores = {}
    
    for criterion in rubric.criteria:
        if signals and criterion.name in signals:
            criterion_scores[criterion.name] = signals[criterion.name]
        else:
            criterion_scores[criterion.name] = _estimate_criterion_score(criterion, lower)
    
    # Weighted total
    total = sum(
        criterion_scores[c.name] * c.weight
        for c in rubric.criteria
    )
    
    # Grade
    if total >= 0.9:
        grade = "excellent"
    elif total >= 0.7:
        grade = "adequate"
    elif total >= 0.5:
        grade = "needs_improvement"
    else:
        grade = "poor"
    
    return {
        "domain": rubric.domain,
        "total_score": round(total, 4),
        "grade": grade,
        "criteria": {name: round(score, 4) for name, score in criterion_scores.items()},
        "weights": {c.name: c.weight for c in rubric.criteria},
        "rubric_source": rubric.source,
    }


def _estimate_criterion_score(criterion: RubricCriterion, text: str) -> float:
    """Estimate a criterion score from text signals."""
    name = criterion.name.lower()
    
    # Domain-specific signal dictionaries
    signals = {
        "correctness": (
            ("test", "pass", "validated", "verified", "assert", "expect", "coverage"),
            ("implement", "complet", "work", "function", "build"),
        ),
        "design": (
            ("clean", "abstract", "interface", "pattern", "modular", "decoupl", "solid"),
            ("structur", "organ", "separate", "component"),
        ),
        "error_handling": (
            ("try", "catch", "except", "graceful", "fallback", "retry", "timeout", "validate"),
            ("error", "fail", "exception"),
        ),
        "testing": (
            ("test", "spec", "assert", "coverage", "tdd", "integration", "e2e", "unittest"),
            ("check", "verify"),
        ),
        "documentation": (
            ("docstring", "comment", "readme", "api doc", "javadoc", "typedoc", "wiki"),
            ("explain", "describe", "note"),
        ),
        "performance": (
            ("optim", "cache", "index", "batch", "parallel", "async", "lazy", "bounded"),
            ("fast", "efficient", "quick"),
        ),
        "root_cause": (
            ("root cause", "five whys", "because", "underlying", "fundamental", "causal"),
            ("caused by", "due to", "reason"),
        ),
        "fix_quality": (
            ("minimal fix", "regression", "test added", "prevent", "systemic"),
            ("fix", "patch", "resolve"),
        ),
        "reproduction": (
            ("reproduce", "minimal repro", "steps to reproduce", "test case", "isolated"),
            ("recreat", "trigger"),
        ),
        "prevention": (
            ("regression test", "anti-pattern", "guard", "prevent", "never again", "systemic"),
            ("watch", "monitor"),
        ),
        "alternatives": (
            ("alternative", "option", "considered", "compared", "versus", "trade-off"),
            ("choice", "select"),
        ),
        "trade_offs": (
            ("trade-off", "cost", "benefit", "pro", "con", "advantage", "disadvantage", "risk"),
            ("balance", "compromise"),
        ),
        "rationale": (
            ("because", "rationale", "reason", "why", "therefore", "justified"),
            ("decided", "chose"),
        ),
        "evidence": (
            ("source", "citation", "reference", "paper", "benchmark", "data", "study", "according"),
            ("evidence", "proof", "show"),
        ),
        "synthesis": (
            ("synthesiz", "conclude", "overall", "combining", "integrate", "summary"),
            ("result", "finding"),
        ),
        "pre_checks": (
            ("smoke test", "pre-check", "before state", "baseline", "health check", "readiness"),
            ("check", "verify"),
        ),
        "monitoring": (
            ("monitor", "alert", "metric", "dashboard", "observ", "log", "trace"),
            ("watch", "track"),
        ),
        "rollback": (
            ("rollback", "revert", "undo", "reverse", "recover", "restore"),
            ("backup", "fallback"),
        ),
    }
    
    excellent_signals = signals.get(name, ((), ()))
    
    excellent_count = sum(1 for s in excellent_signals[0] if s in text)
    adequate_count = sum(1 for s in excellent_signals[1] if s in text)
    
    if excellent_count >= 3:
        return min(1.0, 0.85 + excellent_count * 0.05)
    elif excellent_count >= 1:
        return 0.7 + excellent_count * 0.05
    elif adequate_count >= 2:
        return 0.55 + adequate_count * 0.05
    elif adequate_count >= 1:
        return 0.45
    else:
        return 0.25
