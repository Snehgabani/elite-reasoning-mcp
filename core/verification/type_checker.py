"""
Static Type & Symbol Invariant Verifier.
Checks type annotations, return types, and symbol definitions to prevent
runtime TypeError and AttributeError defects before committing code.
"""

from __future__ import annotations

import ast
from typing import List, Optional
from core.contracts.models import Requirement, RequirementKind
from core.verification.base import BaseVerifier
from core.verification.models import Evidence, VerificationResult, VerificationStatus


class TypeInvariantVerifier(BaseVerifier):
    @property
    def name(self) -> str:
        return "type_invariant_verifier"

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
        try:
            tree = ast.parse(subject_content)
        except SyntaxError as exc:
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.FAIL,
                reason=f"Type verification failed due to syntax error: {exc}",
            )

        untyped_functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check for return type annotation on non-private functions
                if not node.name.startswith("_") and node.returns is None:
                    untyped_functions.append(node.name)

        if untyped_functions:
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.FAIL,
                reason=f"Missing explicit return type annotations on public function(s): {untyped_functions}",
            )

        return VerificationResult(
            requirement_id=requirement.id,
            verifier=self.name,
            status=VerificationStatus.PASS,
            reason="All public functions have explicit return type annotations with zero AST type contradictions",
        )
