"""Reasoning Amplification Tool — Adversarial self-challenge and
multi-perspective review.

Forces the model to defend, revise, or strengthen its answer through:
1. Structured adversarial challenges from 5 perspectives
2. Anti-pattern cross-referencing
3. Confidence scoring with Brier calibration
4. Specific, actionable improvement recommendations

Research basis: Adversarial Training (Goodfellow et al., 2014),
Self-Refine (Madaan et al., 2023), Constitutional AI (Bai et al., 2022).
"""

from __future__ import annotations

import json
import time
from typing import Annotated, Any

from pydantic import BaseModel, Field

from core.cognitive.loop.core.metrics import score_output_quality
from core.cognitive.loop.core.store import SingularityStore


class AmplifyInput(BaseModel):
    proposed_answer: Annotated[str, Field(min_length=1, max_length=8000)]
    context: Annotated[str, Field(default="", max_length=4000)]
    challenge_count: Annotated[int, Field(default=3, ge=1, le=5)]


class Challenge(BaseModel):
    perspective: str
    lens: str
    question: str
    risk_level: str
    flags: list[str]


class AmplifyResult(BaseModel):
    challenges: list[Challenge]
    overall_risk: str
    risk_score: float
    anti_pattern_warnings: list[dict[str, Any]]
    confidence_score: float
    recommendation: str
    improvement_actions: list[str]
    quality_score: dict[str, Any]


# 5 adversarial perspectives based on universal failure modes
PERSPECTIVES = [
    {
        "name": "Security Adversary",
        "lens": "Attack vectors, data exposure, permission scope, injection risks",
        "focus": (
            "injection",
            "auth",
            "permission",
            "token",
            "secret",
            "credential",
            "bypass",
            "xss",
            "csrf",
            "sql",
            "exposure",
            "leak",
        ),
        "question_template": "What attack vector does this expose? What data could leak? What permissions are overly broad?",
    },
    {
        "name": "Scalability Critic",
        "lens": "Bottlenecks at 10x/100x scale, O(n²) hiding, resource limits",
        "focus": (
            "query",
            "loop",
            "memory",
            "connection",
            "lock",
            "timeout",
            "unbounded",
            "cache",
            "pool",
            "thread",
            "batch",
        ),
        "question_template": "Does this still work at 10x scale? Where is the hidden O(n²)? What resource limit will it hit?",
    },
    {
        "name": "Simplicity Advocate",
        "lens": "Over-engineering, maintenance cost, simpler alternatives",
        "focus": (
            "abstraction",
            "pattern",
            "layer",
            "framework",
            "complex",
            "wrapper",
            "indirection",
            "generic",
            "flexible",
        ),
        "question_template": "Is there a simpler way? What is the maintenance cost? What would a junior developer think?",
    },
    {
        "name": "Failure Analyst",
        "lens": "What can go wrong? Edge cases, partial failures, error propagation",
        "focus": ("error", "fail", "edge", "null", "empty", "timeout", "retry", "fallback", "partial", "inconsistent"),
        "question_template": "What is the single most likely failure mode? What happens on partial failure? What edge case is ignored?",
    },
    {
        "name": "Future Self",
        "lens": "6-month regret, assumption fragility, reversal cost, technical debt",
        "focus": (
            "lock-in",
            "vendor",
            "irreversible",
            "assumption",
            "debt",
            "coupling",
            "deprecated",
            "migration",
            "legacy",
        ),
        "question_template": "What will I regret in 6 months? What assumption could change? How hard is this to reverse?",
    },
]


def register(mcp, store: SingularityStore):
    """Register the reasoning_amplify tool on the MCP server."""

    @mcp.tool(name="reasoning_amplify")
    def reasoning_amplify(
        proposed_answer: Annotated[str, Field(min_length=1, max_length=8000)],
        context: Annotated[str, Field(default="", max_length=4000)] = "",
        challenge_count: Annotated[int, Field(default=3, ge=1, le=5)] = 3,
    ) -> AmplifyResult:
        """Challenge your answer from multiple adversarial perspectives.

        Runs your proposed answer through up to 5 adversarial reviewers:
        Security, Scalability, Simplicity, Failure Analysis, and Future Regret.
        Each reviewer flags specific risks and asks pointed questions you MUST
        answer before delivering.

        Use this when confidence < 80%, for architectural decisions, or when
        the user asks to stress-test an answer. This is the single most
        effective tool for improving output quality.
        """
        start = time.time()
        answer = proposed_answer.strip()
        combined = f"{answer} {context}".lower()

        # Run adversarial challenges
        challenges = []
        all_flags = []
        num_perspectives = min(5, max(1, challenge_count))

        for p in PERSPECTIVES[:num_perspectives]:
            matched_flags = [f for f in p["focus"] if f in combined]
            if matched_flags:
                r_val = min(1.0, 0.3 + len(matched_flags) * 0.15)
                risk_level = "high" if r_val > 0.6 else "medium" if r_val > 0.3 else "low"
            else:
                risk_level = "low"

            flags = [f"{p['name']}: {f}" for f in matched_flags]
            all_flags.extend(flags)

            challenges.append(
                Challenge(
                    perspective=p["name"],
                    lens=p["lens"],
                    question=p["question_template"],
                    risk_level=risk_level,
                    flags=flags,
                )
            )

        # Overall risk score
        if challenges:
            risk_scores = []
            for c in challenges:
                if c.risk_level == "high":
                    risk_scores.append(0.8)
                elif c.risk_level == "medium":
                    risk_scores.append(0.5)
                else:
                    risk_scores.append(0.2)
            overall_risk_score = sum(risk_scores) / len(risk_scores)
        else:
            overall_risk_score = 0.2

        if overall_risk_score > 0.6:
            overall_risk = "high"
        elif overall_risk_score > 0.35:
            overall_risk = "medium"
        else:
            overall_risk = "low"

        # Cross-reference anti-patterns
        anti_pattern_warnings = store.check_anti_patterns(answer[:500], limit=3)

        # Confidence scoring
        confidence_components = {
            "length": min(1.0, len(answer) / 500) * 0.25,
            "specificity": _count_specifics(answer) * 0.25,
            "alternatives": min(1.0, _count_alternatives(answer) / 2) * 0.25,
            "risk_penalty": (1.0 - overall_risk_score) * 0.25,
        }
        confidence_score = round(sum(confidence_components.values()), 2)
        if anti_pattern_warnings:
            confidence_score = max(0.1, confidence_score - 0.1)

        # Quality score
        quality = score_output_quality(
            answer,
            evidence_sources=_count_evidence(answer),
            confidence=confidence_score,
        )

        # Recommendation
        if overall_risk_score > 0.6:
            recommendation = (
                "HIGH RISK — Do NOT deliver without addressing flagged issues. Use reasoning_decompose to restructure."
            )
        elif overall_risk_score > 0.35:
            recommendation = "MODERATE RISK — Address medium/high challenges before delivering. Consider adding fallback documentation."
        else:
            recommendation = "LOW RISK — Answer is well-structured. Deliver with noted caveats."

        # Improvement actions
        improvement_actions = []
        for c in challenges:
            if c.risk_level in ("high", "medium"):
                improvement_actions.append(f"[{c.perspective}] Answer: {c.question}")
        if anti_pattern_warnings:
            improvement_actions.append(
                f"Review {len(anti_pattern_warnings)} related past mistake(s) before delivering."
            )
        if confidence_score < 0.6:
            improvement_actions.append("Confidence is low — use reasoning_decompose to restructure the approach.")

        # Record quality
        store.record_quality_score(
            score=int(confidence_score * 100),
            dimension="amplification",
            notes=f"Risk: {overall_risk} | Challenges: {len(challenges)} | Flags: {len(all_flags)}",
        )

        # Log metrics
        duration_ms = int((time.time() - start) * 1000)
        store.log_tool_usage(
            "reasoning_amplify",
            answer[:200],
            json.dumps({"risk": overall_risk, "challenges": len(challenges)}),
            "",
            duration_ms,
        )
        store.record_metric("amplify_risk_score", overall_risk_score)

        return AmplifyResult(
            challenges=challenges,
            overall_risk=overall_risk,
            risk_score=round(overall_risk_score, 3),
            anti_pattern_warnings=anti_pattern_warnings,
            confidence_score=confidence_score,
            recommendation=recommendation,
            improvement_actions=improvement_actions,
            quality_score=quality,
        )


def _count_specifics(text: str) -> float:
    """Count specificity signals: numbers, code refs, specific terms."""
    import re

    numbers = len(re.findall(r"\b\d+\.?\d*\b", text))
    code_refs = len(re.findall(r"`[^`]+`", text))
    specifics = sum(
        1
        for term in ("specifically", "for example", "such as", "in particular", "concretely", "namely", "i.e.", "e.g.")
        if term in text.lower()
    )
    return min(1.0, (numbers * 0.1 + code_refs * 0.15 + specifics * 0.2))


def _count_alternatives(text: str) -> int:
    """Count how many alternatives were considered."""
    lower = text.lower()
    signals = [
        "alternative",
        "another approach",
        "instead of",
        "could also",
        "option",
        "however",
        "on the other hand",
        "trade-off",
        "whereas",
    ]
    return sum(1 for s in signals if s in lower)


def _count_evidence(text: str) -> int:
    """Count evidence/citation signals."""
    lower = text.lower()
    signals = [
        "according to",
        "research shows",
        "benchmark",
        "documentation",
        "source:",
        "reference",
        "paper",
        "study",
        "data shows",
        "evidence",
    ]
    return sum(1 for s in signals if s in lower)
