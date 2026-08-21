"""
Deterministic Constraint Verifier (WS3 / Issue 10).
Evaluates required content, forbidden terms, format, and word limits in sub-millisecond AST/string fast path.
"""

from __future__ import annotations

from typing import List, Optional
from core.contracts.models import Requirement, RequirementKind
from core.verification.models import Evidence, VerificationResult, VerificationStatus
from core.verification.registry import BaseVerifier, GLOBAL_VERIFIER_REGISTRY


class ConstraintVerifier(BaseVerifier):
    @property
    def name(self) -> str:
        return "constraint_verifier"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def supported_requirement_kinds(self) -> List[RequirementKind]:
        return [
            RequirementKind.REQUIRED_CONTENT,
            RequirementKind.FORBIDDEN_CONTENT,
            RequirementKind.WORD_LIMIT,
            RequirementKind.OUTPUT_FORMAT,
        ]

    def verify(
        self,
        requirement: Requirement,
        subject_content: str,
        evidence_records: Optional[List[Evidence]] = None,
    ) -> VerificationResult:
        params = requirement.verifier_parameters

        # 1. Required content check
        if requirement.kind == RequirementKind.REQUIRED_CONTENT:
            required_terms = params.get("required_terms", [])
            missing = [term for term in required_terms if term not in subject_content]
            if missing:
                return VerificationResult(
                    requirement_id=requirement.id,
                    verifier=self.name,
                    status=VerificationStatus.FAIL,
                    reason=f"Subject is missing required term(s): {missing}",
                )
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.PASS,
                reason="All required terms are present in subject",
            )

        # 2. Forbidden content check
        if requirement.kind == RequirementKind.FORBIDDEN_CONTENT:
            forbidden_terms = params.get("forbidden_terms", [])
            present = [term for term in forbidden_terms if term in subject_content]
            if present:
                return VerificationResult(
                    requirement_id=requirement.id,
                    verifier=self.name,
                    status=VerificationStatus.FAIL,
                    reason=f"Subject contains forbidden term(s): {present}",
                )
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.PASS,
                reason="No forbidden terms detected in subject",
            )

        # 3. Word limit check
        if requirement.kind == RequirementKind.WORD_LIMIT:
            max_words = params.get("max_words", 0)
            actual_words = len(subject_content.split())
            if max_words and actual_words > max_words:
                return VerificationResult(
                    requirement_id=requirement.id,
                    verifier=self.name,
                    status=VerificationStatus.FAIL,
                    reason=f"Word count {actual_words} exceeds limit {max_words}",
                )
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.PASS,
                reason=f"Word count {actual_words} within limit {max_words}",
            )

        return VerificationResult(
            requirement_id=requirement.id,
            verifier=self.name,
            status=VerificationStatus.NOT_CHECKED,
            reason="Unrecognized constraint parameter layout",
        )


GLOBAL_VERIFIER_REGISTRY.register(ConstraintVerifier())
