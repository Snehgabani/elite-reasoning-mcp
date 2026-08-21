"""
Speculative Candidate Tree Pruner (AlphaCode 2 / PRM Search).
Evaluates multiple parallel candidate patches/drafts using fast local verifiers,
pruning defective branches in sub-milliseconds before downstream token spend.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field
from core.contracts.models import TaskContract
from core.verification.models import VerificationStatus
from core.verification.registry import VerifierRegistry, GLOBAL_VERIFIER_REGISTRY


class CandidateBranch(BaseModel):
    branch_id: str
    candidate_code: str
    passed_count: int = 0
    failed_count: int = 0
    is_pruned: bool = False
    prune_reason: Optional[str] = None
    score: float = 0.0


class BranchPruningResult(BaseModel):
    total_candidates: int
    pruned_candidates: int
    surviving_candidates: int
    champion_branch: Optional[CandidateBranch] = None
    evaluated_branches: List[CandidateBranch] = Field(default_factory=list)
    schema_version: str = "1.0.0"


def prune_candidate_branches(
    contract: TaskContract,
    candidates: List[str],
    registry: Optional[VerifierRegistry] = None,
) -> BranchPruningResult:
    """Grades candidate code drafts and prunes branches that fail hard invariants."""
    reg = registry or GLOBAL_VERIFIER_REGISTRY
    evaluated = []

    for idx, code in enumerate(candidates, 1):
        branch_id = f"BRANCH-{idx:02d}"
        passed = 0
        failed = 0
        prune_reasons = []

        for req in contract.requirements:
            res = reg.verify_requirement(req, code)
            if res.status == VerificationStatus.PASS:
                passed += 1
            elif res.status == VerificationStatus.FAIL:
                failed += 1
                prune_reasons.append(f"{req.kind.value}: {res.reason}")

        total_reqs = len(contract.requirements) or 1
        score = passed / total_reqs
        is_pruned = failed > 0

        branch = CandidateBranch(
            branch_id=branch_id,
            candidate_code=code,
            passed_count=passed,
            failed_count=failed,
            is_pruned=is_pruned,
            prune_reason="; ".join(prune_reasons) if prune_reasons else None,
            score=score,
        )
        evaluated.append(branch)

    survivors = [b for b in evaluated if not b.is_pruned]
    # Pick champion with highest score or least failures
    champion = max(evaluated, key=lambda b: (b.score, -b.failed_count)) if evaluated else None

    return BranchPruningResult(
        total_candidates=len(candidates),
        pruned_candidates=len(evaluated) - len(survivors),
        surviving_candidates=len(survivors),
        champion_branch=champion,
        evaluated_branches=evaluated,
    )
