"""Host-facing checkpoint reminders derived from persisted workflow evidence.

An MCP server cannot force an IDE model to call it again. This module makes the
next required call explicit on every response and provides a deterministic
state machine clients, rules, hooks, and simulations can audit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ContinuationDirective:
    run_id: str
    phase: str
    checkpoint: str
    required_tool: str
    required_args: dict[str, Any]
    instruction: str
    stop_final_response: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _passing(evidence: list[dict[str, Any]], check: str) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in evidence
            if item.get("check_kind") == check and item.get("verification_status") == "PASS"
        ),
        None,
    )


def _contract_requirements(run: dict[str, Any]) -> tuple[bool, bool, bool]:
    contract = run.get("task_contract") or {}
    constraints = contract.get("constraints") if isinstance(contract, dict) else []
    kinds = {item.get("kind") for item in constraints or [] if isinstance(item, dict)}
    deliverable = str(contract.get("deliverable") or run.get("deliverable") or "").lower() if isinstance(contract, dict) else ""
    is_code = bool(kinds & {"run_tests", "scope_files"}) or any(term in deliverable for term in ("patch", "code", "validation log"))
    return is_code, "scope_files" in kinds, "run_tests" in kinds


def next_continuation(store: Any, run_id: str) -> ContinuationDirective:
    run = store.get_workflow_run(run_id)
    if run is None:
        return ContinuationDirective(
            run_id=run_id,
            phase="UNKNOWN",
            checkpoint="recover",
            required_tool="elite_prepare",
            required_args={"user_prompt": "<current user goal>", "persist": True},
            instruction="The workflow is unavailable. Prepare a new durable workflow before continuing.",
            stop_final_response=True,
        )

    evidence = store.list_workflow_evidence(run_id, limit=200)
    is_code, needs_scope, needs_tests = _contract_requirements(run)
    project_root = "<active repository root>"
    latest_outcome = next((item for item in evidence if item.get("check_kind") == "outcomes"), None)
    failed_unmet = (
        list((latest_outcome.get("payload") or {}).get("unmet") or [])
        if latest_outcome and latest_outcome.get("verification_status") == "FAIL"
        else []
    )
    outcome_index = evidence.index(latest_outcome) if latest_outcome in evidence else len(evidence)

    def _check_is_not_newer(check: str) -> bool:
        index = next(
            (
                position
                for position, item in enumerate(evidence)
                if item.get("check_kind") == check and item.get("verification_status") == "PASS"
            ),
            len(evidence),
        )
        return index > outcome_index

    stale_syntax = any(str(item).startswith("syntax:") for item in failed_unmet) and _check_is_not_newer("syntax")
    stale_scope = any(str(item).startswith("scope_files:") for item in failed_unmet) and _check_is_not_newer("diff")
    stale_tests = any(str(item).startswith("run_tests:") for item in failed_unmet) and _check_is_not_newer("tests")

    if is_code and (_passing(evidence, "syntax") is None or stale_syntax):
        return ContinuationDirective(
            run_id=run_id,
            phase="MID_WORK",
            checkpoint="verify_changed_code",
            required_tool="elite_verify",
            required_args={
                "check": "syntax",
                "run_id": run_id,
                "code": "<current changed code>",
                "project_root": project_root,
            },
            instruction="After the first substantive edit, verify the current changed code. Do not wait until the final response.",
            stop_final_response=True,
        )

    if needs_scope and (_passing(evidence, "diff") is None or stale_scope):
        return ContinuationDirective(
            run_id=run_id,
            phase="MID_WORK",
            checkpoint="verify_repository_scope",
            required_tool="elite_verify",
            required_args={"check": "diff", "run_id": run_id, "project_root": project_root},
            instruction="Verify tracked and untracked file scope after edits and before tests.",
            stop_final_response=True,
        )

    if needs_tests and (_passing(evidence, "tests") is None or stale_tests):
        return ContinuationDirective(
            run_id=run_id,
            phase="POST_WORK",
            checkpoint="run_tests",
            required_tool="elite_verify",
            required_args={
                "check": "tests",
                "run_id": run_id,
                "command": "pytest",
                "project_root": project_root,
            },
            instruction="Run independently captured tests bound to the current repository state.",
            stop_final_response=True,
        )

    outcome = _passing(evidence, "outcomes")
    if outcome is None:
        return ContinuationDirective(
            run_id=run_id,
            phase="FINAL_GATE",
            checkpoint="verify_outcomes",
            required_tool="elite_verify",
            required_args={
                "check": "outcomes",
                "run_id": run_id,
                "draft": "<final draft>",
                **({"project_root": project_root} if is_code else {}),
            },
            instruction="Run the final independent outcome gate. Answer only when it returns PASS/DONE.",
            stop_final_response=True,
        )

    return ContinuationDirective(
        run_id=run_id,
        phase="COMPLETE",
        checkpoint="done",
        required_tool="",
        required_args={},
        instruction="All required checkpoints have current passing evidence. The final response may be delivered.",
        stop_final_response=False,
    )
