"""Calibration Auto-Accumulator — v15 P1 (attacks the biggest measured weak
spot: calibration n=2 → "insufficient_data").

Research base:
- ECE is the standard calibration metric: weighted average deviation between
  stated confidence and empirical accuracy across confidence buckets
  (Naeini et al. 2015; Zylos Research 2026; tianpan.co 2026 production guide).
- "LLM Confidence Calibration in Production": a model saying "90% confident"
  should be right ~900/1000 times — needs volume (n) to measure.

Design: every reasoning_run with a synthesized answer auto-logs ONE resolved
calibration datapoint — confidence = framework_confidence, outcome =
verification_passed (or quality_passed when the verifier was unavailable).
Zero manual steps; n grows with usage; ECE/Brier become meaningful at n≥10
(verdict gate) and strong at n≥50 (target).

Fail-safe: any store error is swallowed — calibration must never break the
reasoning pipeline.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

DEFAULT_DOMAIN = "reasoning"
MIN_VERDICT_N = 10
TARGET_N = 50


def accumulate_calibration(
    store,
    prompt: str,
    confidence: float,
    correct: bool,
    domain: str = DEFAULT_DOMAIN,
) -> dict[str, Any]:
    """Auto-log + auto-resolve one calibration datapoint from a reasoning run.

    prediction_id is derived from prompt + a nanosecond timestamp, so every
    run yields a fresh datapoint (each run is a new sample of the system).
    """
    pred_id = hashlib.sha256(f"auto:{prompt}:{time.time_ns()}".encode()).hexdigest()[:16]
    try:
        store.log_calibration(pred_id, prompt[:2000], float(confidence), domain)
        store.resolve_calibration(pred_id, "auto", bool(correct))
        score = store.get_calibration_score(domain=domain, days=365)
        return {
            "prediction_id": pred_id,
            "confidence": float(confidence),
            "correct": bool(correct),
            "total_predictions": score.get("total_predictions", 0),
            "calibration_status": score.get("calibration_status", "no_data"),
        }
    except Exception:  # fail-safe: calibration never breaks reasoning
        return {
            "prediction_id": pred_id,
            "confidence": float(confidence),
            "correct": bool(correct),
            "total_predictions": None,
            "calibration_status": "error",
        }


def calibration_progress(store, domain: str = DEFAULT_DOMAIN) -> dict[str, Any]:
    """Read-only progress toward the n≥10 verdict gate and n≥50 target."""
    try:
        score = store.get_calibration_score(domain=domain, days=365)
        n = score.get("total_predictions", 0)
        status = score.get("calibration_status", "no_data")
        return {
            "n": n,
            "verdict_gate": MIN_VERDICT_N,
            "target": TARGET_N,
            "to_verdict": max(0, MIN_VERDICT_N - n),
            "to_target": max(0, TARGET_N - n),
            "calibration_status": status,
            "ece": score.get("ece_score"),
            "brier": score.get("brier_score"),
        }
    except Exception:
        return {"n": 0, "calibration_status": "error"}
