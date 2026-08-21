"""
Evidence Completeness & Subject Digest Invalidation Verifier (WS3 / Issue 13).
Validates that attached evidence records are cryptographically bound to the current
subject content digest (SHA-256), rejecting stale or replayed evidence.
"""

from __future__ import annotations

from typing import List, Optional
from core.contracts.models import Requirement, RequirementKind
from core.verification.models import Evidence, VerificationResult, VerificationStatus
from core.verification.registry import BaseVerifier, GLOBAL_VERIFIER_REGISTRY


class EvidenceCompletenessVerifier(BaseVerifier):
    @property
    def name(self) -> str:
        return "evidence_completeness_verifier"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def supported_requirement_kinds(self) -> List[RequirementKind]:
        return [RequirementKind.SECURITY, RequirementKind.COMPATIBILITY]

    def verify(
        self,
        requirement: Requirement,
        subject_content: str,
        evidence_records: Optional[List[Evidence]] = None,
    ) -> VerificationResult:
        if not evidence_records:
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.FAIL,
                reason="No evidence records provided to verify against subject",
            )

        current_digest = Evidence.compute_subject_digest(subject_content)
        stale_evidence = []
        valid_evidence = []

        for ev in evidence_records:
            if ev.subject_digest != current_digest:
                stale_evidence.append(ev.id)
            else:
                valid_evidence.append(ev.id)

        if stale_evidence:
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.FAIL,
                reason=f"Stale evidence detected! Evidence records {stale_evidence} do not match current subject digest {current_digest[:8]}",
                limitations=["Evidence replay or subject modification detected"],
            )

        return VerificationResult(
            requirement_id=requirement.id,
            verifier=self.name,
            status=VerificationStatus.PASS,
            reason=f"All {len(valid_evidence)} evidence records match current subject digest {current_digest[:8]}",
            evidence_ids=valid_evidence,
        )


GLOBAL_VERIFIER_REGISTRY.register(EvidenceCompletenessVerifier())
