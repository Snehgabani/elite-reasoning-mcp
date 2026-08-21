"""Calibration Tool — Track prediction accuracy with Brier scores."""

from __future__ import annotations

import hashlib
import time
from typing import Annotated, Any

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from core.cognitive.loop.core.store import SingularityStore

_CAL_ANNOTATIONS = ToolAnnotations(
    title="Track prediction accuracy",
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)


class CalibrationResult(BaseModel):
    action: str
    prediction_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    interpretation: str = ""


def register(mcp, store: SingularityStore):
    @mcp.tool(name="calibration", annotations=_CAL_ANNOTATIONS)
    def calibration(
        action: str = "predict",
        claim: Annotated[str, Field(default="", max_length=2000)] = "",
        confidence: Annotated[float, Field(default=0.8, ge=0.0, le=1.0)] = 0.8,
        domain: Annotated[str, Field(default="general")] = "general",
        prediction_id: Annotated[str, Field(default="")] = "",
        outcome: Annotated[str, Field(default="")] = "",
        correct: bool = True,
        days: Annotated[int, Field(default=30, ge=1, le=365)] = 30,
    ) -> CalibrationResult:
        """Track prediction accuracy with Brier score. Actions: predict (log with confidence), resolve (record outcome), score (get report). Use when making claims about correctness or performance. Skip for factual lookups.

        Brier: 0.0=perfect, <0.1=good, >0.25=poor.
        """
        if action == "predict":
            if not claim.strip():
                return CalibrationResult(action="predict", interpretation="Claim required.")
            pred_id = hashlib.sha256(f"{claim}:{time.strftime('%Y-%m-%d %H:%M', time.gmtime())}".encode()).hexdigest()[:16]
            store.log_calibration(pred_id, claim, confidence, domain)
            return CalibrationResult(action="predict", prediction_id=pred_id,
                data={"claim": claim, "confidence": confidence},
                interpretation=f"Logged. Use action='resolve' with prediction_id='{pred_id}' when outcome known.")

        elif action == "resolve":
            if not prediction_id.strip():
                return CalibrationResult(action="resolve", interpretation="prediction_id required.")
            resolved = store.resolve_calibration(prediction_id, outcome, correct)
            if not resolved:
                return CalibrationResult(action="resolve", interpretation=f"Not found: {prediction_id}")
            return CalibrationResult(action="resolve", prediction_id=prediction_id,
                data={"outcome": outcome, "correct": correct},
                interpretation="Resolved. Use action='score' for Brier report.")

        elif action == "score":
            result = store.get_calibration_score(domain=domain if domain != "general" else None, days=days)
            if result["total_predictions"] == 0:
                return CalibrationResult(action="score", data=result,
                    interpretation="No resolved predictions yet.")
            brier = result["brier_score"]
            interp = f"Brier={brier:.4f}: {'Good' if brier < 0.1 else 'Fair' if brier < 0.25 else 'Poor'}"
            return CalibrationResult(action="score", data=result, interpretation=interp)

        return CalibrationResult(action=action, interpretation=f"Unknown: {action}. Use predict, resolve, or score.")
