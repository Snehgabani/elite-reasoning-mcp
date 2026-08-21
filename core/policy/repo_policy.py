"""
Repository Security and Workflow Policy Engine (WS8 / Phase 5).
Parses .elite-policy.yml files to enforce repo-level constraints on all compiled contracts.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import yaml
from pydantic import BaseModel, Field
from core.contracts.models import Requirement, RequirementKind, RequirementSeverity, TaskContract


class RepoPolicy(BaseModel):
    policy_name: str = "default_repo_policy"
    mandatory_allowed_files: List[str] = Field(default_factory=list)
    forbidden_terms: List[str] = Field(default_factory=list)
    required_test_command: Optional[str] = None
    max_repair_attempts: int = 2
    schema_version: str = "1.0.0"

    @classmethod
    def load_from_file(cls, policy_path: Path) -> RepoPolicy:
        path = Path(policy_path)
        if not path.exists():
            return cls()
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)

    def apply_to_contract(self, contract: TaskContract) -> TaskContract:
        # Enforce repo-level forbidden terms
        for term in self.forbidden_terms:
            req_id = f"POLICY-FORBIDDEN-{term}"
            if not any(r.id == req_id for r in contract.requirements):
                contract.requirements.append(
                    Requirement(
                        id=req_id,
                        kind=RequirementKind.FORBIDDEN_CONTENT,
                        source_text=f"Repo Policy: forbidden term {term}",
                        interpretation=f"Repo-wide policy bans term: {term}",
                        severity=RequirementSeverity.CRITICAL,
                        verifier="constraint_verifier",
                        verifier_parameters={"forbidden_terms": [term]},
                    )
                )

        # Enforce repo-level test command
        if self.required_test_command:
            req_id = "POLICY-TEST-CMD"
            if not any(r.kind == RequirementKind.TEST_COMMAND for r in contract.requirements):
                contract.requirements.append(
                    Requirement(
                        id=req_id,
                        kind=RequirementKind.TEST_COMMAND,
                        source_text=f"Repo Policy: run {self.required_test_command}",
                        interpretation=f"Repo policy enforces test execution: {self.required_test_command}",
                        severity=RequirementSeverity.REQUIRED,
                        verifier="test_command_verifier",
                        verifier_parameters={"command": self.required_test_command},
                    )
                )

        contract.max_repair_attempts = min(contract.max_repair_attempts, self.max_repair_attempts)
        return contract
