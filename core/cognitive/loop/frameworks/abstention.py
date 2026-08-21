"""Calibrated Abstention — v15 P0 #3.

Research base:
- "Know Your Limits: A Survey of Abstention in Large Language Models"
  (TACL 2025, aclanthology.org/2025.tacl-1.26) — abstention is selective
  prediction: withhold output below a confidence threshold; abstention
  should route to information acquisition, not a dead end.
- AbstentionBench (arXiv 2503.xxxxx) — reasoning fine-tuning DEGRADES
  abstention (~24% worse): reasoning models over-answer. A post-hoc
  calibrated gate is therefore a cheap, principled fix on top of any
  reasoning pipeline.
- Confidence-based abstention (selective prediction) — abstain when the
  decision signal falls below a threshold.

Design (transparent, weighted signal composite — not vibes):
    abstention_score = 0.50*verification + 0.25*agreement
                     + 0.15*confidence + 0.10*quality
    Hard rule: verification < 0.35  -> ABSTAIN regardless (a verified-FAIL
    answer must not be served as if confident).
    Soft rule: composite < 0.55     -> ABSTAIN.
    Fail-open: verification is None (LLM down) -> NO abstention decision
    (the caller already warns; we never silently kill an answer that had no
    chance to be verified).
    Direct mode: never abstain (trivial fast path).

When abstaining, the caller KEEPS the answer (abstention leads to further
information acquisition per the TACL survey) but flags it loudly so a human
does not treat it as confirmed.
"""

from __future__ import annotations

from typing import Any

# Weights sum to 1.0; verification dominates because step-level evidence is the
# strongest signal a PRM-style critic provides (GenPRM lineage, P0 #2).
_W_VERIFICATION = 0.50
_W_AGREEMENT = 0.25
_W_CONFIDENCE = 0.15
_W_QUALITY = 0.10

ABSTAIN_COMPOSITE_THRESHOLD = 0.55
ABSTAIN_HARD_VERIFICATION_THRESHOLD = 0.35


def calibrated_abstention(
    verification_score: float | None,
    consensus_agreement: float = 0.0,
    confidence: float = 0.0,
    quality_score: float = 0.0,
    mode: str = "amplified",
    abstain_composite_threshold: float = ABSTAIN_COMPOSITE_THRESHOLD,
    abstain_hard_verification_threshold: float = ABSTAIN_HARD_VERIFICATION_THRESHOLD,
) -> dict[str, Any]:
    """Decide whether the pipeline should abstain (flag low-confidence output).

    Returns {"abstained": bool, "reason": str, "abstention_score": float|None}.
    Score is None when no verification evidence exists (fail-open).
    """
    if mode == "direct":
        return {
            "abstained": False,
            "reason": "",
            "abstention_score": None,
        }

    if verification_score is None:
        # Fail-open: no verification evidence -> no abstention decision.
        return {
            "abstained": False,
            "reason": "",
            "abstention_score": None,
        }

    composite = (
        _W_VERIFICATION * verification_score
        + _W_AGREEMENT * consensus_agreement
        + _W_CONFIDENCE * confidence
        + _W_QUALITY * quality_score
    )

    if verification_score < abstain_hard_verification_threshold:
        return {
            "abstained": True,
            "reason": (
                f"Step verification failed hard ({verification_score:.2f} < "
                f"{abstain_hard_verification_threshold:.2f}); answer may be "
                "unreliable — verify independently before trusting."
            ),
            "abstention_score": round(composite, 3),
        }

    if composite < abstain_composite_threshold:
        return {
            "abstained": True,
            "reason": (
                f"Low confidence composite ({composite:.2f} < "
                f"{abstain_composite_threshold:.2f}) — verification "
                f"{verification_score:.2f}, agreement {consensus_agreement:.2f}, "
                f"confidence {confidence:.2f}; treat answer as unconfirmed."
            ),
            "abstention_score": round(composite, 3),
        }

    return {
        "abstained": False,
        "reason": "",
        "abstention_score": round(composite, 3),
    }
