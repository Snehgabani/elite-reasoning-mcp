"""
Four-State Verification and Evidence Domain Models (WS3 / Issue 8).
Enforces PASS, FAIL, UNKNOWN, NOT_CHECKED verification states with cryptographic
SHA-256 subject digest bindings to prevent stale evidence replay.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List
from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_CHECKED = "NOT_CHECKED"


class Evidence(BaseModel):
    id: str = Field(..., description="Unique evidence identifier")
    kind: str = Field(..., description="Evidence category (e.g. test_log, git_diff, quote, ast_parse)")
    producer: str = Field(..., description="Tool or verifier that produced this evidence")
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    subject_digest: str = Field(..., description="SHA-256 hash of the subject code/draft evaluated")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Raw verifiable payload (e.g. exit_code, stdout)")
    redactions: List[str] = Field(default_factory=list, description="Redacted secret patterns")
    artifact_digest: str = Field(default="", description="Digest of external log file or diff")

    @classmethod
    def compute_subject_digest(cls, content: str) -> str:
        """Helper to compute SHA-256 hash of draft content or diff."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class VerificationResult(BaseModel):
    requirement_id: str = Field(..., description="Target requirement ID from TaskContract")
    verifier: str = Field(..., description="Verifier class or plugin name")
    verifier_version: str = Field(default="1.0.0")
    status: VerificationStatus = Field(..., description="One of PASS, FAIL, UNKNOWN, NOT_CHECKED")
    reason: str = Field(..., description="Detailed explanation of the verdict")
    evidence_ids: List[str] = Field(default_factory=list, description="Linked evidence record IDs")
    limitations: List[str] = Field(default_factory=list, description="Any environmental or tool limitations")
    duration_ms: float = Field(default=0.0, description="Verification latency in milliseconds")
