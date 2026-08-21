"""
Python AST Syntax Verifier (WS3 / Issue 10).
Deterministic Python AST parser gate verifying syntactic validity with SHA-256 evidence binding.
"""

from __future__ import annotations

import ast
from typing import List, Optional
from core.contracts.models import Requirement, RequirementKind
from core.verification.models import Evidence, VerificationResult, VerificationStatus
from core.verification.registry import BaseVerifier, GLOBAL_VERIFIER_REGISTRY


class PythonSyntaxVerifier(BaseVerifier):
    @property
    def name(self) -> str:
        return "python_syntax_verifier"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def supported_requirement_kinds(self) -> List[RequirementKind]:
        return [RequirementKind.COMPATIBILITY, RequirementKind.OUTPUT_FORMAT]

    def verify(
        self,
        requirement: Requirement,
        subject_content: str,
        evidence_records: Optional[List[Evidence]] = None,
    ) -> VerificationResult:
        digest = Evidence.compute_subject_digest(subject_content)

        try:
            ast.parse(subject_content)
            evidence = Evidence(
                id=f"EV-SYNTAX-{digest[:8]}",
                kind="ast_parse",
                producer=self.name,
                subject_digest=digest,
                payload={"valid_syntax": True},
            )
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.PASS,
                reason="Python AST parsed successfully with 0 syntax errors",
                evidence_ids=[evidence.id],
            )
        except SyntaxError as exc:
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.FAIL,
                reason=f"Python SyntaxError on line {exc.lineno}: {exc.msg}",
            )


GLOBAL_VERIFIER_REGISTRY.register(PythonSyntaxVerifier())
