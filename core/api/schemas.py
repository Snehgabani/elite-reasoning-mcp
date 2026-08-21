"""
Versioned Public MCP Response Contracts (WS5 / Issue 14).
Provides typed, versioned request/response schemas for the five core MCP tools.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from core.contracts.models import TaskContract
from core.verification.models import VerificationResult, VerificationStatus


class BaseMcpResponse(BaseModel):
    schema_version: str = "1.0.0"
    status: Literal["SUCCESS", "FAILED", "UNKNOWN"] = "SUCCESS"
    duration_ms: float = 0.0


class ElitePrepareResponse(BaseMcpResponse):
    task_id: str
    task_contract: TaskContract
    risk_tier: str
    topology_modules: List[str] = Field(default_factory=list)
    injected_lessons_count: int = 0
    note: str = ""


class EliteVerifyResponse(BaseMcpResponse):
    overall_status: VerificationStatus
    results: List[VerificationResult] = Field(default_factory=list)
    passed_count: int = 0
    failed_count: int = 0
    unknown_count: int = 0
    not_checked_count: int = 0
    prevented_completion: bool = False
    evidence_bundle_digest: Optional[str] = None


class EliteMemoryResponse(BaseMcpResponse):
    action: str
    items_count: int = 0
    lessons: List[Dict[str, Any]] = Field(default_factory=list)
    trust_state: str = "approved"


class EliteProgressResponse(BaseMcpResponse):
    task_id: str
    current_step: int
    total_steps: int
    completed_outcomes: List[str] = Field(default_factory=list)
    remaining_outcomes: List[str] = Field(default_factory=list)
