"""
Base Verifier Protocol (WS3).
Defines the abstract base class for all deterministic requirement verifiers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from core.contracts.models import Requirement, RequirementKind
from core.verification.models import Evidence, VerificationResult


class BaseVerifier(ABC):
    """Abstract base class for deterministic requirement verifiers."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    @abstractmethod
    def supported_requirement_kinds(self) -> List[RequirementKind]:
        pass

    @abstractmethod
    def verify(
        self,
        requirement: Requirement,
        subject_content: str,
        evidence_records: Optional[List[Evidence]] = None,
    ) -> VerificationResult:
        pass
