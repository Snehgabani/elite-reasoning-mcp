"""Bias & Red Flag Detection — Cognitive bias scanner and anti-sycophancy guard.

Implements research-backed techniques for detecting and mitigating:
- Sycophancy (agreeing with user when wrong)
- 10 common cognitive biases that degrade reasoning quality
- Confidence-evidence mismatch (Dunning-Kruger detection)
- Contradictions between claims and evidence

Research: SYCON-Bench (EMNLP 2025), CAU SM (ICLR 2025),
Kamruzzaman & Kim (RANLP 2025), MBIAS (WASSA 2024).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class RedFlag:
    """A detected reasoning flaw."""

    bias_type: str
    severity: str  # critical, high, medium, low
    description: str
    evidence: str
    recommendation: str


@dataclass
class BiasScanResult:
    """Complete bias scan result."""

    red_flags: list[RedFlag] = field(default_factory=list)
    sycophancy_score: float = 0.0
    confidence_evidence_gap: float = 0.0
    overall_risk: str = "low"
    anti_sycophancy_prompt: str = ""
    recommendations: list[str] = field(default_factory=list)


# ── Cognitive Bias Patterns ─────────────────────────────────

BIAS_PATTERNS = {
    "anchoring": {
        "signals": (
            "first approach",
            "obvious choice",
            "clearly the best",
            "naturally",
            "obviously",
            "the only way",
            "everyone knows",
        ),
        "description": "Anchoring on first idea without exploring alternatives",
        "severity": "high",
        "recommendation": "Enumerate at least 2 alternatives before committing.",
    },
    "confirmation_bias": {
        "signals": (
            "proves that",
            "confirms",
            "as expected",
            "just as I thought",
            "validates our approach",
            "supports the decision",
        ),
        "description": "Only seeking/presenting supporting evidence",
        "severity": "high",
        "recommendation": "Actively search for contradictory evidence. What would disprove this?",
    },
    "sunk_cost": {
        "signals": (
            "already invested",
            "we've spent",
            "too far to",
            "already built",
            "can't change now",
            "committed to",
        ),
        "description": "Continuing because of past investment rather than future value",
        "severity": "medium",
        "recommendation": "Evaluate based on future value only. Past costs are irrelevant.",
    },
    "authority_bias": {
        "signals": (
            "expert says",
            "industry standard",
            "best practice",
            "everyone uses",
            "google does it",
            "netflix uses",
            "amazon recommends",
        ),
        "description": "Appealing to authority instead of evaluating on merits",
        "severity": "medium",
        "recommendation": "Evaluate the reasoning, not the source. Does it apply to YOUR context?",
    },
    "availability_bias": {
        "signals": (
            "recent outage",
            "last time",
            "I just read",
            "everyone's talking about",
            "trending",
            "news about",
            "went viral",
        ),
        "description": "Overweighting recent/vivid examples",
        "severity": "medium",
        "recommendation": "Check base rates. Is this actually common or just memorable?",
    },
    "survivorship_bias": {
        "signals": ("successful companies", "winners all", "top performers", "the ones that made it", "best-in-class"),
        "description": "Only looking at successes, ignoring failures",
        "severity": "medium",
        "recommendation": "What about the failures? What did they do differently?",
    },
    "false_precision": {
        "signals": (r"\b\d{2,}\.\d{3,}\b", r"exactly \d+%", r"precisely \d+"),
        "description": "Specific numbers without justification or measurement",
        "severity": "low",
        "recommendation": "Use ranges or confidence intervals instead of false precision.",
    },
    "halo_effect": {
        "signals": ("amazing", "perfect", "best ever", "incredible", "game-changing", "revolutionary", "silver bullet"),
        "description": "One positive attribute coloring all judgment",
        "severity": "low",
        "recommendation": "Evaluate each aspect independently. What are the trade-offs?",
    },
    "bandwagon": {
        "signals": (
            "everyone is using",
            "industry is moving",
            "all the cool kids",
            "you'd be crazy not to",
            "no-brainer",
            "adopted by",
        ),
        "description": "Following the crowd without independent evaluation",
        "severity": "medium",
        "recommendation": "Would you choose this if nobody else was using it?",
    },
    "dunning_kruger": {
        "signals": ("simple fix", "easy solution", "trivial", "just do", "obviously", "no need to", "anyone can"),
        "description": "High confidence with low demonstrated understanding",
        "severity": "high",
        "recommendation": "Demonstrate understanding before committing. What edge cases exist?",
    },
}

# Anti-sycophancy prompt (research: third-person perspective reduces sycophancy by 63.8%)
ANTI_SYCOPHANCY_PROMPT = (
    "You are an objective analyst with no stake in the outcome. "
    "Evaluate the answer on its own merits. Do NOT agree with the user's "
    "stated assumptions unless independently verified. If the user's premise "
    "is wrong, say so directly with evidence."
)


def scan_for_biases(text: str, context: str = "") -> list[RedFlag]:
    """Scan text for cognitive bias patterns.

    Args:
        text: The answer/plan to scan
        context: The original prompt/user request (for sycophancy detection)
    """
    flags = []
    lower_text = text.lower()

    for bias_name, pattern in BIAS_PATTERNS.items():
        signals = pattern["signals"]
        matched = []

        for signal in signals:
            if signal.startswith(r"\b"):
                # Regex pattern
                if re.search(signal, text):
                    matched.append(signal)
            elif signal in lower_text:
                matched.append(signal)

        if matched:
            flags.append(
                RedFlag(
                    bias_type=bias_name.replace("_", " ").title(),
                    severity=pattern["severity"],
                    description=pattern["description"],
                    evidence=f"Detected signals: {', '.join(matched[:3])}",
                    recommendation=pattern["recommendation"],
                )
            )

    return flags


def detect_sycophancy(answer: str, user_prompt: str) -> float:
    """Detect sycophancy — agreeing with user's assumptions without analysis.

    Returns a score 0-1 where higher = more sycophantic.
    """
    score = 0.0
    lower_answer = answer.lower()
    lower_prompt = user_prompt.lower()

    # Signal 1: Excessive agreement markers
    agreement_signals = [
        "you're right",
        "exactly",
        "absolutely",
        "great point",
        "that's correct",
        "i agree",
        "you're absolutely right",
        "spot on",
        "well said",
        "perfect analysis",
    ]
    agreement_count = sum(1 for s in agreement_signals if s in lower_answer)
    score += min(0.3, agreement_count * 0.1)

    # Signal 2: Echoing user's framing without analysis
    # Extract key claims from user prompt
    user_keywords = [w for w in lower_prompt.split() if len(w) > 5]
    echo_count = sum(1 for w in user_keywords if w in lower_answer)
    if len(user_keywords) > 0:
        echo_ratio = echo_count / len(user_keywords)
        if echo_ratio > 0.5:
            score += 0.2

    # Signal 3: No counterpoints or alternatives
    counterpoint_signals = [
        "however",
        "but",
        "alternatively",
        "on the other hand",
        "although",
        "contradicting",
        "disagree",
        "challenge",
        "risk",
        "downside",
        "trade-off",
        "concern",
    ]
    has_counterpoints = any(s in lower_answer for s in counterpoint_signals)
    if not has_counterpoints:
        score += 0.2

    # Signal 4: Overly positive framing without substance
    hype_signals = ["great idea", "excellent approach", "brilliant", "innovative", "cutting-edge", "best-in-class"]
    hype_count = sum(1 for s in hype_signals if s in lower_answer)
    if hype_count >= 2:
        score += 0.15

    return min(1.0, score)


def detect_confidence_evidence_gap(answer: str, confidence: float) -> float:
    """Detect Dunning-Kruger effect: high confidence with low evidence.

    Returns gap score 0-1 where higher = bigger gap.
    """
    lower = answer.lower()

    # Count evidence signals
    evidence_signals = [
        "because",
        "evidence",
        "data shows",
        "research",
        "benchmark",
        "measured",
        "tested",
        "verified",
        "according to",
        "source",
        "citation",
        "documentation",
        "reference",
        "proven",
    ]
    evidence_count = sum(1 for s in evidence_signals if s in lower)

    # Count uncertainty markers
    uncertainty_signals = [
        "maybe",
        "possibly",
        "uncertain",
        "unclear",
        "assumption",
        "might",
        "could be",
        "unclear",
        "not sure",
        "estimated",
    ]
    uncertainty_count = sum(1 for s in uncertainty_signals if s in lower)

    # Evidence score (0-1)
    evidence_score = min(1.0, evidence_count * 0.15)

    # Gap = high confidence + low evidence
    gap = max(0, confidence - evidence_score)

    # Reduce gap if uncertainty is acknowledged
    gap = max(0, gap - uncertainty_count * 0.05)

    return min(1.0, gap)


def run_bias_scan(answer: str, user_prompt: str = "", confidence: float = 0.7) -> BiasScanResult:
    """Complete bias scan of an answer.

    Combines cognitive bias detection, sycophancy scoring, and
    confidence-evidence gap analysis.
    """
    # 1. Scan for cognitive biases
    red_flags = scan_for_biases(answer, user_prompt)

    # 2. Sycophancy detection
    sycophancy = detect_sycophancy(answer, user_prompt) if user_prompt else 0.0

    # 3. Confidence-evidence gap
    ce_gap = detect_confidence_evidence_gap(answer, confidence)

    # 4. Add sycophancy as a red flag if high
    if sycophancy > 0.4:
        red_flags.append(
            RedFlag(
                bias_type="Sycophancy",
                severity="high" if sycophancy > 0.6 else "medium",
                description="Agreeing with user's assumptions without independent analysis",
                evidence=f"Sycophancy score: {sycophancy:.2f}",
                recommendation="Use third-person analytical perspective. Challenge the user's premise with evidence.",
            )
        )

    # 5. Add confidence-evidence gap as a red flag if high
    if ce_gap > 0.4:
        red_flags.append(
            RedFlag(
                bias_type="Confidence-Evidence Gap",
                severity="high" if ce_gap > 0.6 else "medium",
                description=f"High confidence ({confidence:.0%}) with insufficient evidence backing",
                evidence=f"Gap score: {ce_gap:.2f}",
                recommendation="Add evidence sources or reduce confidence. Acknowledge uncertainty explicitly.",
            )
        )

    # 6. Determine overall risk
    critical_count = sum(1 for f in red_flags if f.severity == "critical")
    high_count = sum(1 for f in red_flags if f.severity == "high")

    if critical_count > 0:
        overall_risk = "critical"
    elif high_count >= 2:
        overall_risk = "high"
    elif high_count >= 1 or len(red_flags) >= 3:
        overall_risk = "medium"
    else:
        overall_risk = "low"

    # 7. Generate recommendations
    recommendations = []
    if sycophancy > 0.3:
        recommendations.append("Apply anti-sycophancy guard: evaluate on merits, not user alignment.")
    if ce_gap > 0.3:
        recommendations.append("Bridge confidence-evidence gap: add sources or lower confidence.")
    if any(f.bias_type == "Anchoring" for f in red_flags):
        recommendations.append("Break anchoring: enumerate 2+ alternatives before deciding.")
    if any(f.bias_type == "Confirmation Bias" for f in red_flags):
        recommendations.append("Actively seek contradictory evidence.")

    return BiasScanResult(
        red_flags=red_flags,
        sycophancy_score=round(sycophancy, 3),
        confidence_evidence_gap=round(ce_gap, 3),
        overall_risk=overall_risk,
        anti_sycophancy_prompt=ANTI_SYCOPHANCY_PROMPT if sycophancy > 0.3 else "",
        recommendations=recommendations,
    )
