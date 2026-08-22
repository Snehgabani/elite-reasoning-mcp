"""Personalized tool playbook for one prompt.

Cheap models fail when 90 tools sit in context (schema tax + random selection).
This module never recommends the legacy catalog. It returns at most three
ordered calls on the core surface, plus expected outcomes the verifier scores.

Honest limit: MCP cannot stop a host model from answering without tools.
Enforcement is fail-closed verify (REPEAT) plus a one-step next action —
not LangGraph wrapping a model we do not own.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from core.reasoning.task_contract import NextAction, TaskContract


CORE_TOOLS = ("elite_prepare", "elite_verify", "elite_memory")


@dataclass(frozen=True)
class PlaybookStep:
    """One required or optional call. `tool='host_work'` means the model writes."""

    index: int
    tool: str
    args: dict[str, Any]
    required: bool
    instruction: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExpectedOutcome:
    """A benchmark the verifier can score independently of the model's self-report."""

    id: str
    statement: str
    check: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compile_playbook(contract: TaskContract) -> tuple[PlaybookStep, ...]:
    """Ordered path for this prompt. The host may only use listed tools."""
    steps: list[PlaybookStep] = []
    n = 1
    nxt: NextAction = contract.next_action

    if nxt == "evidence":
        steps.append(
            PlaybookStep(
                index=n,
                tool="elite_verify",
                args={"check": "evidence", "query": contract.goal},
                required=True,
                instruction="Fetch verbatim quotes before writing. No quote, no citation.",
            )
        )
        n += 1

    if nxt == "verify_tests":
        steps.append(
            PlaybookStep(
                index=n,
                tool="host_work",
                args={},
                required=True,
                instruction=f"Produce the deliverable: {contract.deliverable}",
            )
        )
        n += 1
        steps.append(
            PlaybookStep(
                index=n,
                tool="elite_verify",
                args={
                    "check": "tests",
                    "command": "pytest",
                    "run_id": "<run_id from elite_prepare>",
                    "project_root": "<active repository root>",
                },
                required=True,
                instruction=(
                    "Run allowlisted tests and bind the result to the repository state. "
                    "A prose claim that tests passed is not evidence."
                ),
            )
        )
        n += 1
    else:
        steps.append(
            PlaybookStep(
                index=n,
                tool="host_work",
                args={},
                required=True,
                instruction=f"Produce the deliverable: {contract.deliverable}. Obey every constraint.",
            )
        )
        n += 1

    steps.append(
        PlaybookStep(
            index=n,
            tool="elite_verify",
            args={
                "check": "outcomes",
                "run_id": "<run_id from elite_prepare>",
                "draft": "<your draft>",
                **(
                    {"project_root": "<active repository root>"}
                    if any(c.kind in {"run_tests", "scope_files"} for c in contract.constraints)
                    else {}
                ),
            },
            required=True,
            instruction=(
                "Independent gate. If action=REPEAT, do not answer the user — fix unmet items and verify again."
            ),
        )
    )
    return tuple(steps[:4])


def compile_expected_outcomes(contract: TaskContract) -> tuple[ExpectedOutcome, ...]:
    """Turn the contract into a scoring rubric. This is the prompt's benchmark."""
    outcomes: list[ExpectedOutcome] = [
        ExpectedOutcome(
            id="goal",
            statement=f"The draft satisfies the goal: {contract.goal}",
            check="constraints",
        ),
        ExpectedOutcome(
            id="deliverable",
            statement=f"The deliverable is present: {contract.deliverable}",
            check="constraints",
        ),
    ]
    for item in contract.constraints:
        outcomes.append(
            ExpectedOutcome(
                id=item.id,
                statement=item.description,
                check="constraints" if item.kind != "run_tests" else "tests",
            )
        )
    if contract.next_action == "evidence":
        outcomes.append(
            ExpectedOutcome(
                id="grounded",
                statement="Factual claims have verbatim quotes and live URLs from elite_verify(check='evidence').",
                check="grounding",
            )
        )
    return tuple(outcomes[:8])


def allowed_tools_for(contract: TaskContract) -> tuple[str, ...]:
    """Tools the host is permitted to call for this run. Everything else is noise."""
    allowed = ["elite_verify"]
    if contract.next_action == "evidence":
        allowed.insert(0, "elite_verify")
    # Memory is optional and cheap; never required.
    if "memory" in contract.goal.lower() or "remember" in " ".join(contract.do_not).lower():
        allowed.append("elite_memory")
    # Deduplicate, never include admin or the 90-tool catalog.
    seen: list[str] = []
    for name in allowed:
        if name not in seen and name in CORE_TOOLS:
            seen.append(name)
    return tuple(seen) or ("elite_verify",)


def verify_outcomes(draft: str, contract: TaskContract) -> dict[str, Any]:
    """Independent goal gate. The model does not get to score itself."""
    from core.reasoning.constraint_check import check_draft

    report = check_draft(draft or "", contract)
    passed = bool(report.passed)
    action = "DONE" if passed else "REPEAT"
    instruction = (
        "Goal met. You may answer the user."
        if passed
        else (
            "REPEAT. Do not present a final answer. Fix unmet outcomes, then call "
            "elite_verify(check='outcomes', run_id=..., draft=...) again."
        )
    )
    return {
        "passed": passed,
        "action": action,
        "pass_rate": report.pass_rate,
        "unmet": list(report.unmet),
        "instruction": instruction,
        "expected_outcomes": [item.to_dict() for item in compile_expected_outcomes(contract)],
        "results": [item.to_dict() for item in report.results],
    }


def playbook_card(contract: TaskContract) -> dict[str, Any]:
    """Compact card a small model can follow without browsing the catalog."""
    steps = compile_playbook(contract)
    outcomes = compile_expected_outcomes(contract)
    allowed = allowed_tools_for(contract)
    return {
        "allowed_tools": list(allowed),
        "forbidden": ("Do not call any other MCP tool. Do not call the same tool twice unless verify returned REPEAT."),
        "playbook": [step.to_dict() for step in steps],
        "expected_outcomes": [item.to_dict() for item in outcomes],
        "repeat_until": "elite_verify(check='outcomes') returns action=DONE",
        "escape_hatch": (
            "This server cannot physically stop the host model from skipping tools. "
            "Treat action=REPEAT as a hard stop. Presenting an answer after REPEAT is a protocol violation."
        ),
    }
