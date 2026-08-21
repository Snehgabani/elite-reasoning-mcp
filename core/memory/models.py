"""
Trusted Memory Domain Models (WS4 / Phase 2).
Provides quarantine lifecycle, provenance tracking, sensitivity states,
and anti-poisoning data models for persistent agent memory.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class TrustState(str, Enum):
    OBSERVED = "observed"
    QUARANTINED = "quarantined"
    APPROVED = "approved"
    ACTIVE = "active"
    STALE = "stale"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MemoryScope(str, Enum):
    PROJECT = "project"
    USER = "user"
    GLOBAL = "global"


class SensitivityState(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE_SECRET = "sensitive_secret"


class TrustedMemory(BaseModel):
    id: str
    content: str
    normalized_content: str
    lesson_type: str = "guideline"
    scope: MemoryScope = MemoryScope.PROJECT
    project_id: Optional[str] = None
    trust_state: TrustState = TrustState.QUARANTINED
    sensitivity_state: SensitivityState = SensitivityState.INTERNAL
    provenance: str = "verified_outcome"
    producer: str = "elite_engine"
    evidence_ids: List[str] = Field(default_factory=list)
    contradiction_group: Optional[str] = None
    successful_uses: int = 0
    harmful_uses: int = 0
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    expires_at: Optional[float] = None
    schema_version: str = "1.0.0"
