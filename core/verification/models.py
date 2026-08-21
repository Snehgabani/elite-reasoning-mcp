"""Versioned evidence and four-state verification models.

Transport success is not verification success. A tool call can return normally
while the requested check is unknown or was not executed, so core verification
uses four explicit states instead of overloading a boolean.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    """Outcome of a check, independent of whether the tool call succeeded."""

    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_CHECKED = "NOT_CHECKED"


class EvidenceRecord(BaseModel):
    """A bounded evidence summary bound to the exact checked subject."""

    schema_version: str = "1.0"
    id: str
    kind: str
    producer: str
    collected_at: str
    subject_digest: str
    artifact_digest: str
    payload: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def subject_digest(kind: str, content: str) -> str:
    """Bind evidence to a subject type and exact content without retaining it."""
    normalized_kind = (kind or "unknown").strip().lower()
    encoded = f"elite-subject-v1\0{normalized_kind}\0{content or ''}".encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def evidence_record(
    *,
    kind: str,
    producer: str,
    subject_digest_value: str,
    payload: dict[str, Any],
    limitations: list[str] | None = None,
) -> EvidenceRecord:
    """Create a content-addressed evidence summary.

    The ID is deterministic for the producer, checked subject, and payload. The
    collection timestamp is intentionally excluded from the ID so retries over
    identical evidence can be recognized.
    """
    bounded_payload = dict(payload)
    artifact_material = {
        "kind": kind,
        "producer": producer,
        "subject_digest": subject_digest_value,
        "payload": bounded_payload,
    }
    artifact_hex = hashlib.sha256(_canonical_json(artifact_material).encode("utf-8")).hexdigest()
    return EvidenceRecord(
        id=f"ev_{artifact_hex[:20]}",
        kind=kind,
        producer=producer,
        collected_at=datetime.now(timezone.utc).isoformat(),
        subject_digest=subject_digest_value,
        artifact_digest="sha256:" + artifact_hex,
        payload=bounded_payload,
        limitations=list(limitations or []),
    )


def status_from_bool(value: bool) -> VerificationStatus:
    return VerificationStatus.PASS if value else VerificationStatus.FAIL


class Evidence(BaseModel):
    """Compatibility evidence model used by requirement-oriented plugin verifiers."""

    id: str
    kind: str
    producer: str
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    subject_digest: str
    payload: dict[str, Any] = Field(default_factory=dict)
    redactions: list[str] = Field(default_factory=list)
    artifact_digest: str = ""

    @classmethod
    def compute_subject_digest(cls, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class VerificationResult(BaseModel):
    """Requirement-level result used by the verifier plugin SDK."""

    requirement_id: str
    verifier: str
    verifier_version: str = "1.0.0"
    status: VerificationStatus
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    duration_ms: float = 0.0
