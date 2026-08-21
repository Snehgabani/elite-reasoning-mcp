"""
Source-Span Requirement Extractor & TaskContract Compiler (WS2 / Issue 7).
Extracts typed constraints from user instructions with exact character spans,
assigns verifiers, and normalizes TaskContracts without inventing non-existent rules.
"""

from __future__ import annotations

import hashlib
import re
from typing import List
from core.contracts.models import (
    EvidenceRequirement,
    Requirement,
    RequirementKind,
    RequirementSeverity,
    RequirementStatus,
    RiskTier,
    TaskContract,
)


class ContractCompiler:
    """Compiles natural language instructions into verifiable TaskContracts with exact source spans."""

    def compile(self, prompt: str, goal_hint: str = "") -> TaskContract:
        requirements: List[Requirement] = []
        evidence_reqs: List[EvidenceRequirement] = []

        # 1. Extract Required Content / Terms (e.g. 'must include OAuth2')
        for match in re.finditer(
            r"\b(?:must include|must contain|must have)\s+(['\"][^'\"]+['\"]|[a-zA-Z0-9_\-\.\/]+)",
            prompt,
            re.IGNORECASE,
        ):
            raw_match = match.group(0)
            term = match.group(1).strip(" '\".,;:!?")
            span = match.span()
            req_id = f"REQ-CONTENT-{self._hash_span(raw_match)}"
            requirements.append(
                Requirement(
                    id=req_id,
                    kind=RequirementKind.REQUIRED_CONTENT,
                    source_text=raw_match,
                    source_start=span[0],
                    source_end=span[1],
                    interpretation=f"Draft must contain exact term: {term}",
                    severity=RequirementSeverity.CRITICAL,
                    verifier="constraint_verifier",
                    verifier_parameters={"required_terms": [term]},
                    extraction_confidence=0.98,
                    status=RequirementStatus.CONFIRMED,
                )
            )

        # 2. Extract Forbidden Content / Anti-patterns (e.g. 'do not use bcrypt')
        for match in re.finditer(
            r"\b(?:do not use|never use|forbidden to use|avoid)\s+(['\"][^'\"]+['\"]|[a-zA-Z0-9_\-\.\/]+)",
            prompt,
            re.IGNORECASE,
        ):
            raw_match = match.group(0)
            term = match.group(1).strip(" '\".,;:!?")
            span = match.span()
            req_id = f"REQ-FORBIDDEN-{self._hash_span(raw_match)}"
            requirements.append(
                Requirement(
                    id=req_id,
                    kind=RequirementKind.FORBIDDEN_CONTENT,
                    source_text=raw_match,
                    source_start=span[0],
                    source_end=span[1],
                    interpretation=f"Draft must NOT contain term or anti-pattern: {term}",
                    severity=RequirementSeverity.CRITICAL,
                    verifier="constraint_verifier",
                    verifier_parameters={"forbidden_terms": [term]},
                    extraction_confidence=0.98,
                    status=RequirementStatus.CONFIRMED,
                )
            )

        # 3. Extract File Scope Limits (e.g. 'modify only auth.py')
        for match in re.finditer(
            r"\b(?:modify only|touch only|only edit)\s+([a-zA-Z0-9_\-\.\/,\s]+?)(?=\.|\band\b|$)",
            prompt,
            re.IGNORECASE,
        ):
            raw_match = match.group(0)
            raw_files = match.group(1).strip()
            files = [f.strip(" `'\".,;:!?") for f in re.split(r"[,;\s]+", raw_files) if f.strip(" `'\".,;:!?")]
            span = match.span()
            req_id = f"REQ-SCOPE-{self._hash_span(raw_match)}"
            requirements.append(
                Requirement(
                    id=req_id,
                    kind=RequirementKind.ALLOWED_FILES,
                    source_text=raw_match,
                    source_start=span[0],
                    source_end=span[1],
                    interpretation=f"Git diff must modify only allowed files: {files}",
                    severity=RequirementSeverity.CRITICAL,
                    verifier="git_diff_verifier",
                    verifier_parameters={"allowed_files": files},
                    extraction_confidence=0.95,
                    status=RequirementStatus.CONFIRMED,
                )
            )
            evidence_reqs.append(
                EvidenceRequirement(
                    id=f"EV-DIFF-{req_id}",
                    kind="git_diff",
                    producer="git",
                    required_for_requirements=[req_id],
                )
            )

        # 4. Extract Test Execution Requirements (e.g. 'run tests', 'run pytest', 'pytest')
        for match in re.finditer(r"\b(?:run tests|run pytest|pytest|npm test)\b", prompt, re.IGNORECASE):
            raw_match = match.group(0)
            span = match.span()
            req_id = f"REQ-TEST-{self._hash_span(raw_match)}"
            requirements.append(
                Requirement(
                    id=req_id,
                    kind=RequirementKind.TEST_COMMAND,
                    source_text=raw_match,
                    source_start=span[0],
                    source_end=span[1],
                    interpretation="Automated test suite must execute and return exit code 0",
                    severity=RequirementSeverity.REQUIRED,
                    verifier="test_command_verifier",
                    verifier_parameters={"command": raw_match.lower()},
                    extraction_confidence=0.95,
                    status=RequirementStatus.CONFIRMED,
                )
            )
            evidence_reqs.append(
                EvidenceRequirement(
                    id=f"EV-LOG-{req_id}",
                    kind="test_log",
                    producer="test_runner",
                    required_for_requirements=[req_id],
                )
            )

        # Risk tier routing
        has_critical = any(r.severity == RequirementSeverity.CRITICAL for r in requirements)
        risk = RiskTier.CRITICAL if has_critical else RiskTier.STANDARD

        goal = goal_hint or (prompt[:120] + "..." if len(prompt) > 120 else prompt)

        return TaskContract(
            schema_version="1.0.0",
            goal=goal,
            deliverable="Evidence-verified artifact or code diff",
            requirements=requirements,
            evidence_requirements=evidence_reqs,
            risk_tier=risk,
            stop_conditions=["All critical requirements PASS", "No unresolved UNKNOWN state"],
            max_repair_attempts=2,
        )

    def _hash_span(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
