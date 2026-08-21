"""
Git Diff Scope Verifier (WS3 / Issue 12).
Evaluates unified git diffs against allowed_files and forbidden_files policies,
detects unintended file touch escapes and manifest modifications.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Set
from core.contracts.models import Requirement, RequirementKind
from core.verification.models import Evidence, VerificationResult, VerificationStatus
from core.verification.registry import BaseVerifier, GLOBAL_VERIFIER_REGISTRY


class GitDiffScopeVerifier(BaseVerifier):
    @property
    def name(self) -> str:
        return "git_diff_verifier"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def supported_requirement_kinds(self) -> List[RequirementKind]:
        return [RequirementKind.ALLOWED_FILES, RequirementKind.FORBIDDEN_FILES]

    def _extract_modified_files(self, diff_text: str) -> Set[str]:
        modified = set()
        for line in diff_text.splitlines():
            # Match --- a/path/to/file or +++ b/path/to/file or diff --git a/path b/path
            m = re.match(r"^(?:\+\+\+ b\/|--- a\/|diff --git a\/)(\S+)", line)
            if m:
                path = m.group(1).strip()
                if path != "/dev/null":
                    modified.add(path)
        return modified

    def verify(
        self,
        requirement: Requirement,
        subject_content: str,
        evidence_records: Optional[List[Evidence]] = None,
    ) -> VerificationResult:
        diff_text = subject_content
        modified_files = self._extract_modified_files(diff_text)

        # If subject is a simple file list string rather than unified diff
        if not modified_files and diff_text.strip():
            for line in diff_text.splitlines():
                f = line.strip().lstrip("+-* ").strip()
                if f and not f.startswith("#"):
                    modified_files.add(f)

        params = requirement.verifier_parameters
        allowed_files = set(params.get("allowed_files", []))
        forbidden_files = set(params.get("forbidden_files", []))

        # Check allowed files constraint
        if requirement.kind == RequirementKind.ALLOWED_FILES:
            if not allowed_files:
                return VerificationResult(
                    requirement_id=requirement.id,
                    verifier=self.name,
                    status=VerificationStatus.NOT_CHECKED,
                    reason="No allowed files pattern specified in requirement",
                )

            # Check if any modified file is not in allowed files (supporting basename matches)
            disallowed = []
            for mf in modified_files:
                basename = Path(mf).name
                if mf not in allowed_files and basename not in allowed_files:
                    disallowed.append(mf)

            if disallowed:
                return VerificationResult(
                    requirement_id=requirement.id,
                    verifier=self.name,
                    status=VerificationStatus.FAIL,
                    reason=f"Diff modified unauthorized file(s) outside allowed scope: {disallowed}",
                )

            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.PASS,
                reason=f"All modified files {sorted(modified_files)} are within allowed scope",
            )

        # Check forbidden files constraint
        if requirement.kind == RequirementKind.FORBIDDEN_FILES:
            violations = []
            for mf in modified_files:
                basename = Path(mf).name
                if mf in forbidden_files or basename in forbidden_files:
                    violations.append(mf)

            if violations:
                return VerificationResult(
                    requirement_id=requirement.id,
                    verifier=self.name,
                    status=VerificationStatus.FAIL,
                    reason=f"Diff modified forbidden file(s): {violations}",
                )

            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.PASS,
                reason="No forbidden files were modified in diff",
            )

        return VerificationResult(
            requirement_id=requirement.id,
            verifier=self.name,
            status=VerificationStatus.NOT_CHECKED,
            reason="Unrecognized scope requirement kind",
        )


GLOBAL_VERIFIER_REGISTRY.register(GitDiffScopeVerifier())
