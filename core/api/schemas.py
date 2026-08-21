"""Versioned response schemas for the five-tool MCP surface."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from core.verification.models import EvidenceRecord, VerificationStatus


class WorkflowStep(BaseModel):
    index: int
    name: str
    action: str
    status: str
    evidence: str = ""


class PrepareResult(BaseModel):
    status: Literal["ok"] = "ok"
    run_id: str
    persisted: bool
    intent: str
    complexity: int
    budget_tier: str
    confidence: float
    goal: str = ""
    deliverable: str = ""
    next_action: str = "none"
    constraints: list[str] = Field(default_factory=list)
    do_not: list[str] = Field(default_factory=list)
    stop_when: list[str] = Field(default_factory=list)
    task_contract: dict[str, Any] = Field(default_factory=dict)
    playbook: list[dict[str, Any]] = Field(default_factory=list)
    expected_outcomes: list[dict[str, Any]] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    repeat_until: str = ""
    steps: list[WorkflowStep]
    validation_gates: list[str]
    evidence_requirements: list[str]
    memory_context: list[dict[str, Any]]
    capability_warnings: list[str]
    warnings: list[str] = Field(default_factory=list)


class ProgressResult(BaseModel):
    status: Literal["ok"] = "ok"
    run_id: str
    workflow_status: str
    steps: list[WorkflowStep]
    warnings: list[str] = Field(default_factory=list)


class VerifyResult(BaseModel):
    """Transport result plus an explicit evidence outcome.

    `status=ok` means the MCP call returned normally. `verification_status`
    describes what the check established and must be used for completion gates.
    """

    status: Literal["ok"] = "ok"
    schema_version: str = "1.1"
    check: str
    verification_status: VerificationStatus = VerificationStatus.NOT_CHECKED
    subject_digest: str = ""
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    data: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class MemoryResult(BaseModel):
    status: Literal["ok"] = "ok"
    action: str
    memory_id: int | None = None
    quarantined: bool | None = None
    deleted: bool | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AdminResult(BaseModel):
    status: Literal["ok"] = "ok"
    action: str
    data: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
