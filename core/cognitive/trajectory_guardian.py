"""
Trajectory Guardian & Anti-Amnesia State Machine (FSM).
Prevents LLMs from 'single-turn tool decay' (calling MCP once at start and forgetting mid-turn).
Maintains a strict epoch-clock, cryptographic gate nonces, and forces intermediate verifiers.
"""

from __future__ import annotations

import enum
import hashlib
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field


class TrajectoryStage(str, enum.Enum):
    UNINITIALIZED = "UNINITIALIZED"
    CONTRACT_COMPILED = "CONTRACT_COMPILED"
    IN_PROGRESS_EDIT = "IN_PROGRESS_EDIT"
    MID_VERIFY_PENDING = "MID_VERIFY_PENDING"
    MID_VERIFIED = "MID_VERIFIED"
    TEST_PENDING = "TEST_PENDING"
    TEST_VERIFIED = "TEST_VERIFIED"
    ATTESTED_COMPLETE = "ATTESTED_COMPLETE"


class GateToken(BaseModel):
    epoch: int
    stage: TrajectoryStage
    token: str
    issued_at: float = Field(default_factory=time.time)
    required_next_tool: str


class TrajectoryState(BaseModel):
    session_id: str
    current_stage: TrajectoryStage = TrajectoryStage.UNINITIALIZED
    epoch_clock: int = 0
    gate_tokens: List[GateToken] = Field(default_factory=list)
    actions_since_last_verify: int = 0
    mcp_tool_calls_count: int = 0
    native_tool_calls_count: int = 0
    verified_files: Set[str] = Field(default_factory=set)
    unverified_edits_count: int = 0
    active_contract_goal: str = ""
    amnesia_detected: bool = False
    last_error_message: Optional[str] = None

    def calculate_mcp_density(self) -> float:
        total = self.mcp_tool_calls_count + self.native_tool_calls_count
        if total == 0:
            return 1.0
        return round(self.mcp_tool_calls_count / total, 3)


class TrajectoryGuardian:
    """Singleton/Instance FSM tracking active multi-turn agent sessions and enforcing continuous step-locks."""

    def __init__(self):
        self._sessions: Dict[str, TrajectoryState] = {}

    def get_or_create_session(self, session_id: str = "default") -> TrajectoryState:
        if session_id not in self._sessions:
            self._sessions[session_id] = TrajectoryState(session_id=session_id)
        return self._sessions[session_id]

    def record_pre_edit_contract(self, session_id: str, goal: str) -> GateToken:
        """Checkpoint 1: Compiles contract and advances stage."""
        state = self.get_or_create_session(session_id)
        state.epoch_clock += 1
        state.mcp_tool_calls_count += 1
        state.current_stage = TrajectoryStage.CONTRACT_COMPILED
        state.active_contract_goal = goal
        state.actions_since_last_verify = 0
        state.amnesia_detected = False

        token_hash = hashlib.sha256(f"{session_id}:{state.epoch_clock}:CONTRACT".encode()).hexdigest()[:12]
        token = GateToken(
            epoch=state.epoch_clock,
            stage=TrajectoryStage.CONTRACT_COMPILED,
            token=f"GATE-CONTRACT-{token_hash}",
            required_next_tool="elite_verify(check='syntax'|'cegis') after any code change",
        )
        state.gate_tokens.append(token)
        return token

    def record_file_edit(self, session_id: str, file_path: str) -> Dict[str, Any]:
        """Triggered whenever a file modification occurs."""
        state = self.get_or_create_session(session_id)
        state.epoch_clock += 1
        state.native_tool_calls_count += 1
        state.current_stage = TrajectoryStage.MID_VERIFY_PENDING
        state.actions_since_last_verify += 1
        state.unverified_edits_count += 1
        state.verified_files.discard(file_path)

        if state.actions_since_last_verify >= 2:
            state.amnesia_detected = True

        return {
            "session_id": session_id,
            "stage": state.current_stage.value,
            "actions_since_verify": state.actions_since_last_verify,
            "amnesia_warning": state.amnesia_detected,
            "mcp_density": state.calculate_mcp_density(),
            "mandatory_action": f"Call elite_verify(check='syntax') on {file_path}",
        }

    def record_verification_check(self, session_id: str, check_type: str, passed: bool) -> Optional[GateToken]:
        """Checkpoint 2 & 3: Records deterministic verification pass/fail."""
        state = self.get_or_create_session(session_id)
        state.epoch_clock += 1
        state.mcp_tool_calls_count += 1

        if not passed:
            state.current_stage = TrajectoryStage.MID_VERIFY_PENDING
            state.last_error_message = f"Verification `{check_type}` failed."
            return None

        if check_type in ("syntax", "cegis", "types", "outline"):
            state.current_stage = TrajectoryStage.MID_VERIFIED
            state.actions_since_last_verify = 0
            state.amnesia_detected = False
            token_hash = hashlib.sha256(f"{session_id}:{state.epoch_clock}:MID".encode()).hexdigest()[:12]
            token = GateToken(
                epoch=state.epoch_clock,
                stage=TrajectoryStage.MID_VERIFIED,
                token=f"GATE-MIDVERIFY-{token_hash}",
                required_next_tool="elite_verify(check='tests', command='pytest ...') before final text",
            )
            state.gate_tokens.append(token)
            return token

        elif check_type in ("tests", "outcomes", "constraints"):
            state.current_stage = TrajectoryStage.TEST_VERIFIED
            state.actions_since_last_verify = 0
            state.amnesia_detected = False
            token_hash = hashlib.sha256(f"{session_id}:{state.epoch_clock}:TEST".encode()).hexdigest()[:12]
            token = GateToken(
                epoch=state.epoch_clock,
                stage=TrajectoryStage.TEST_VERIFIED,
                token=f"GATE-TESTVERIFY-{token_hash}",
                required_next_tool="attest_workflow_completion or final reply",
            )
            state.gate_tokens.append(token)
            return token

        return None

    def validate_completion_attestation(self, session_id: str) -> Tuple[bool, str]:
        """Enforces that an agent cannot conclude without passing both mid-turn and post-edit gates."""
        state = self.get_or_create_session(session_id)

        # Check if contract was compiled
        has_contract = any(t.stage == TrajectoryStage.CONTRACT_COMPILED for t in state.gate_tokens)
        if not has_contract:
            return False, "HARD INVARIANT VIOLATION: No TaskContract was compiled (Missing Checkpoint 1)."

        # Check if edits happened without mid-turn verification
        if state.unverified_edits_count > 0 and state.current_stage not in (
            TrajectoryStage.MID_VERIFIED,
            TrajectoryStage.TEST_VERIFIED,
        ):
            return False, (
                f"AMNESIA DECAY DETECTED: {state.unverified_edits_count} unverified file edits exist. "
                "You must call elite_verify(check='syntax'|'cegis') before finalizing."
            )

        # Check if test verification was run
        has_test_pass = any(t.stage == TrajectoryStage.TEST_VERIFIED for t in state.gate_tokens)
        if not has_test_pass and state.unverified_edits_count > 0:
            return False, "HARD INVARIANT VIOLATION: No test execution receipt found (Missing Checkpoint 3)."

        # Check MCP Tool Density across trajectory
        if state.native_tool_calls_count > 0 and state.mcp_tool_calls_count < 2:
            return False, (
                f"INSUFFICIENT MCP DENSITY ({state.calculate_mcp_density() * 100:.1f}%): You called elite_reason at start "
                "but skipped intermediate MCP verifiers. You must execute all playbook verification steps."
            )

        state.current_stage = TrajectoryStage.ATTESTED_COMPLETE
        return True, "All 3 trajectory checkpoints verified successfully."

    def build_recency_directive(self, session_id: str = "default") -> Dict[str, Any]:
        """Generates dynamic recency-weighted next-action headers for LLM tool returns."""
        state = self.get_or_create_session(session_id)
        stage = state.current_stage

        if stage == TrajectoryStage.UNINITIALIZED:
            next_action = (
                "call_mcp_tool(ServerName='elite-reasoning-mcp', ToolName='elite_reason', Arguments={'task': '...'})"
            )
            step_name = "Checkpoint 1 [PRE-EDIT]"
        elif stage in (TrajectoryStage.CONTRACT_COMPILED, TrajectoryStage.MID_VERIFIED):
            next_action = "Modify files or call elite_verify(check='syntax'|'cegis') immediately after code edits"
            step_name = "Checkpoint 2 [DURING-EDIT]"
        elif stage == TrajectoryStage.MID_VERIFY_PENDING:
            next_action = "🚨 CRITICAL: Call elite_verify(check='syntax', code=...) NOW before continuing"
            step_name = "Checkpoint 2 [MID-VERIFY-REQUIRED]"
        elif stage == TrajectoryStage.TEST_PENDING:
            next_action = "Call elite_verify(check='tests', command='pytest ...') before final text"
            step_name = "Checkpoint 3 [POST-EDIT-TESTS]"
        elif stage == TrajectoryStage.TEST_VERIFIED:
            next_action = "Deliver final text with passing verification receipt"
            step_name = "Checkpoint 3 [RECEIPT-READY]"
        else:
            next_action = "Trajectory complete"
            step_name = "COMPLETE"

        return {
            "epoch": state.epoch_clock,
            "stage": stage.value,
            "step_name": step_name,
            "mandatory_next_action": next_action,
            "amnesia_warning": state.amnesia_detected,
            "unverified_edits": state.unverified_edits_count,
        }


# Global Singleton Guardian Instance
GLOBAL_TRAJECTORY_GUARDIAN = TrajectoryGuardian()
