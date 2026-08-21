"""
Core Domain Models for Task Contracts and Typed Requirement Extraction (WS2 / Issue 6).
Provides immutable Pydantic models with explicit source spans, severity ratings,
and machine-checkable verifier parameters.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RequirementKind(str, Enum):
    REQUIRED_CONTENT = "required_content"
    FORBIDDEN_CONTENT = "forbidden_content"
    OUTPUT_FORMAT = "output_format"
    WORD_LIMIT = "word_limit"
    ALLOWED_FILES = "allowed_files"
    FORBIDDEN_FILES = "forbidden_files"
    DEPENDENCY_POLICY = "dependency_policy"
    COMPATIBILITY = "compatibility"
    TEST_COMMAND = "test_command"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ROBUSTNESS = "robustness"
    CITATION_GROUNDING = "citation_grounding"
    DIRECT_ANSWER = "direct_answer"
    HUMAN_APPROVAL = "human_approval"


class RiskTier(str, Enum):
    TRIVIAL = "trivial"
    LOW = "low"
    STANDARD = "standard"
    HIGH_RISK = "high_risk"
    CRITICAL = "critical"


class RequirementSeverity(str, Enum):
    CRITICAL = "critical"
    REQUIRED = "required"
    PREFERENCE = "preference"


class RequirementStatus(str, Enum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    WAIVED = "waived"


class Requirement(BaseModel):
    id: str = Field(..., description="Unique deterministic requirement ID")
    kind: RequirementKind = Field(..., description="Classification category of the requirement")
    source_text: str = Field(..., description="Verbatim text span from the prompt")
    source_start: int = Field(default=0, description="Start character index in original prompt")
    source_end: int = Field(default=0, description="End character index in original prompt")
    interpretation: str = Field(..., description="Machine-checkable interpretation")
    severity: RequirementSeverity = Field(default=RequirementSeverity.REQUIRED)
    verifier: Optional[str] = Field(default=None, description="Assigned verifier plugin name")
    verifier_parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters passed to verifier")
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    status: RequirementStatus = Field(default=RequirementStatus.CONFIRMED)


class EvidenceRequirement(BaseModel):
    id: str = Field(..., description="Evidence requirement ID")
    kind: str = Field(..., description="Expected evidence kind (e.g. test_log, git_diff, quote)")
    producer: Optional[str] = Field(default=None)
    required_for_requirements: List[str] = Field(default_factory=list)


class TaskContract(BaseModel):
    schema_version: str = Field(default="1.0.0")
    goal: str = Field(..., description="High-level goal statement")
    deliverable: str = Field(..., description="Expected deliverable artifact description")
    requirements: List[Requirement] = Field(default_factory=list)
    non_goals: List[str] = Field(default_factory=list)
    evidence_requirements: List[EvidenceRequirement] = Field(default_factory=list)
    risk_tier: RiskTier = Field(default=RiskTier.STANDARD)
    stop_conditions: List[str] = Field(default_factory=list)
    max_repair_attempts: int = Field(default=2, ge=0, le=5)
