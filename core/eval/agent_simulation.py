"""
Simulated LLM Agent Trajectory Environment.
Tests multi-turn agent behavior under context dilution, mid-turn tool forgetting,
and unverified self-certification, verifying that Elite deterministic gates catch omissions.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from core.contracts.compiler import ContractCompiler
from core.verification.models import VerificationStatus
from core.verification.registry import VerifierRegistry, GLOBAL_VERIFIER_REGISTRY


class AgentArchetype(str, Enum):
    LAZY_AMNESIAC = "lazy_amnesiac"  # Calls elite_reason once, forgets mid-turn tools
    HALLUCINATING = "hallucinating"  # Claims tests passed without running them
    STEP_LOCKED_ELITE = "step_locked_elite"  # Follows all 3 checkpoints deterministically


class TrajectoryStep(BaseModel):
    step_index: int
    action_type: str  # "tool_call", "file_edit", "user_reply"
    tool_name: Optional[str] = None
    tool_arguments: Dict[str, Any] = Field(default_factory=dict)
    output_summary: str = ""
    is_compliant: bool = True


class SimulationResult(BaseModel):
    archetype: AgentArchetype
    total_steps: int
    checkpoint_1_passed: bool  # Pre-edit contract call
    checkpoint_2_passed: bool  # Mid-turn AST & CEGIS verification
    checkpoint_3_passed: bool  # Post-edit test & receipt generation
    is_final_outcome_safe: bool
    omission_reasons: List[str] = Field(default_factory=list)
    trajectory: List[TrajectoryStep] = Field(default_factory=list)
    latency_ms: float = 0.0


class AgentSimulationEnvironment:
    """Simulates multi-turn IDE agent executions and audits adherence to 3-checkpoint lifecycle."""

    def __init__(self, registry: Optional[VerifierRegistry] = None):
        self.registry = registry or GLOBAL_VERIFIER_REGISTRY
        self.compiler = ContractCompiler()

    def run_simulation(
        self,
        prompt: str,
        archetype: AgentArchetype,
        candidate_code: str,
    ) -> SimulationResult:
        t0 = time.perf_counter()
        contract = self.compiler.compile(prompt)
        trajectory: List[TrajectoryStep] = []
        omissions = []

        step_idx = 1
        # Step 1: Pre-edit Checkpoint
        has_cp1 = True
        trajectory.append(
            TrajectoryStep(
                step_index=step_idx,
                action_type="tool_call",
                tool_name="elite_reason",
                tool_arguments={"task": prompt},
                output_summary=f"Compiled contract with {len(contract.requirements)} requirements",
                is_compliant=True,
            )
        )
        step_idx += 1

        # Step 2: Mid-turn Editing
        trajectory.append(
            TrajectoryStep(
                step_index=step_idx,
                action_type="file_edit",
                output_summary="Agent modified source code file",
                is_compliant=True,
            )
        )
        step_idx += 1

        has_cp2 = False
        if archetype == AgentArchetype.STEP_LOCKED_ELITE:
            # Invokes syntax and cegis verifiers
            syn_res = self.registry.get("python_syntax_verifier").verify(contract.requirements[0], candidate_code)
            cegis_res = self.registry.get("cegis_property_verifier").verify(contract.requirements[0], candidate_code)
            has_cp2 = syn_res.status == VerificationStatus.PASS and cegis_res.status == VerificationStatus.PASS
            trajectory.append(
                TrajectoryStep(
                    step_index=step_idx,
                    action_type="tool_call",
                    tool_name="elite_verify",
                    tool_arguments={"check": "cegis"},
                    output_summary=f"CEGIS Status: {cegis_res.status.value}",
                    is_compliant=has_cp2,
                )
            )
            step_idx += 1
        else:
            omissions.append("Agent forgot Checkpoint 2 (skipped mid-turn AST & CEGIS verification)")

        # Step 3: Post-edit Verification & Response
        has_cp3 = False
        if archetype == AgentArchetype.STEP_LOCKED_ELITE:
            # Invokes test command verifier and checks constraints
            passed_all = True
            for req in contract.requirements:
                vres = self.registry.verify_requirement(req, candidate_code)
                if vres.status == VerificationStatus.FAIL:
                    passed_all = False
            has_cp3 = passed_all
            trajectory.append(
                TrajectoryStep(
                    step_index=step_idx,
                    action_type="tool_call",
                    tool_name="elite_verify",
                    tool_arguments={"check": "constraints"},
                    output_summary=f"Contract verification passed: {has_cp3}",
                    is_compliant=has_cp3,
                )
            )
            step_idx += 1
        elif archetype == AgentArchetype.HALLUCINATING:
            omissions.append("Agent hallucinated test completion without calling elite_verify(check='tests')")
        else:
            omissions.append("Agent forgot Checkpoint 3 (delivered answer without verification receipt)")

        duration_ms = (time.perf_counter() - t0) * 1000
        is_safe = has_cp1 and has_cp2 and has_cp3

        return SimulationResult(
            archetype=archetype,
            total_steps=len(trajectory),
            checkpoint_1_passed=has_cp1,
            checkpoint_2_passed=has_cp2,
            checkpoint_3_passed=has_cp3,
            is_final_outcome_safe=is_safe,
            omission_reasons=omissions,
            trajectory=trajectory,
            latency_ms=round(duration_ms, 2),
        )
