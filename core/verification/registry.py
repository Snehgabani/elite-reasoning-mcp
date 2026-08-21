"""
Verifier Protocol and Central Verifier Registry (WS3 / Issue 9).
Provides abstract verifier interface, four-state execution dispatch,
and registry lookup for deterministic and environmental verifiers.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from core.contracts.models import Requirement, RequirementKind
from core.verification.models import Evidence, VerificationResult, VerificationStatus


class BaseVerifier(ABC):
    """Abstract base class for all Elite verifiers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique verifier identifier."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Semantic version string of the verifier."""
        pass

    @property
    @abstractmethod
    def supported_requirement_kinds(self) -> List[RequirementKind]:
        """List of RequirementKinds handled by this verifier."""
        pass

    @abstractmethod
    def verify(
        self,
        requirement: Requirement,
        subject_content: str,
        evidence_records: Optional[List[Evidence]] = None,
    ) -> VerificationResult:
        """Executes verification and returns four-state VerificationResult."""
        pass


class VerifierRegistry:
    """Thread-safe verifier registry managing first-party and plugin verifiers."""

    def __init__(self):
        self._verifiers: Dict[str, BaseVerifier] = {}
        self._kind_mapping: Dict[RequirementKind, str] = {}
        self._builtins_loaded: bool = False

    def _ensure_builtins(self):
        if self._builtins_loaded:
            return
        self._builtins_loaded = True
        try:
            from core.verification.completeness import EvidenceCompletenessVerifier
            from core.verification.constraints import ConstraintVerifier
            from core.verification.git_diff import GitDiffScopeVerifier
            from core.verification.syntax import PythonSyntaxVerifier
            from core.verification.test_command import TestCommandVerifier

            self.register(ConstraintVerifier())
            self.register(PythonSyntaxVerifier())
            self.register(TestCommandVerifier())
            self.register(GitDiffScopeVerifier())
            self.register(EvidenceCompletenessVerifier())
        except Exception:
            pass

    def register(self, verifier: BaseVerifier, default_for_kinds: Optional[List[RequirementKind]] = None):
        self._verifiers[verifier.name] = verifier
        if default_for_kinds:
            for kind in default_for_kinds:
                self._kind_mapping[kind] = verifier.name
        else:
            for kind in verifier.supported_requirement_kinds:
                if kind not in self._kind_mapping:
                    self._kind_mapping[kind] = verifier.name

    def get(self, name: str) -> Optional[BaseVerifier]:
        self._ensure_builtins()
        return self._verifiers.get(name)

    def get_for_kind(self, kind: RequirementKind) -> Optional[BaseVerifier]:
        self._ensure_builtins()
        name = self._kind_mapping.get(kind)
        return self._verifiers.get(name) if name else None

    def verify_requirement(
        self,
        requirement: Requirement,
        subject_content: str,
        evidence_records: Optional[List[Evidence]] = None,
    ) -> VerificationResult:
        self._ensure_builtins()
        t0 = time.perf_counter()

        verifier = None
        if requirement.verifier:
            verifier = self.get(requirement.verifier)
        if not verifier:
            verifier = self.get_for_kind(requirement.kind)

        if not verifier:
            return VerificationResult(
                requirement_id=requirement.id,
                verifier="unregistered",
                status=VerificationStatus.NOT_CHECKED,
                reason=f"No matching verifier registered for requirement kind: {requirement.kind.value}",
                duration_ms=round((time.perf_counter() - t0) * 1000, 3),
            )

        try:
            result = verifier.verify(requirement, subject_content, evidence_records)
            result.duration_ms = round((time.perf_counter() - t0) * 1000, 3)
            return result
        except Exception as exc:
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=verifier.name,
                verifier_version=verifier.version,
                status=VerificationStatus.UNKNOWN,
                reason=f"Verifier execution error: {type(exc).__name__}: {exc}",
                limitations=["Unhandled runtime exception during verification"],
                duration_ms=round((time.perf_counter() - t0) * 1000, 3),
            )


# Global Default Registry
GLOBAL_VERIFIER_REGISTRY = VerifierRegistry()
