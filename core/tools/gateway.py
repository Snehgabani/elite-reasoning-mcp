"""Compact, typed v2 MCP gateway tools.

The default profile intentionally exposes a small task-oriented surface. The
legacy profile keeps the individual tools available for established clients.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

import os
import shlex
import subprocess

from core.orchestration.capabilities import build_capability_registry
from core.orchestration.workflow_run import build_workflow_run
from core.runtime import runtime_identity
from core.tools.doctor import build_doctor_report
from core.tools.errors import validation_error
from core.verification.models import EvidenceRecord, VerificationStatus, evidence_record, status_from_bool, subject_digest

_ALLOWED_TEST_PREFIXES = (
    "pytest",
    "python -m pytest",
    "python3 -m pytest",
    "ruff",
    "python -m ruff",
    "python3 -m ruff",
)


def _run_allowlisted_command(command: str, *, cwd: str = "") -> dict[str, Any]:
    """Run a tiny allowlisted test/lint command. Never a generic shell."""
    cleaned = (command or "").strip()
    if not cleaned:
        raise validation_error("command is required for check=tests.")
    lowered = cleaned.lower()
    if not any(lowered == prefix or lowered.startswith(prefix + " ") for prefix in _ALLOWED_TEST_PREFIXES):
        return {
            "passed": False,
            "executed": False,
            "reason": "command is not on the pytest/ruff allowlist",
            "command": cleaned,
        }
    if os.environ.get("ELITE_ALLOW_TEST_COMMAND", "").strip() != "1":
        return {
            "passed": False,
            "executed": False,
            "reason": "set ELITE_ALLOW_TEST_COMMAND=1 to run allowlisted tests locally",
            "command": cleaned,
        }
    try:
        completed = subprocess.run(
            shlex.split(cleaned),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            cwd=cwd or None,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"passed": False, "executed": False, "reason": str(exc)[:200], "command": cleaned}
    output = ((completed.stdout or "") + (completed.stderr or ""))[-1500:]
    return {
        "passed": completed.returncode == 0,
        "executed": True,
        "returncode": completed.returncode,
        "output": output,
        "command": cleaned,
    }


class WorkflowStep(BaseModel):
    index: int
    name: str
    action: str
    status: str
    evidence: str = ""


class PrepareResult(BaseModel):
    status: Literal["ok"] = "ok"
    run_id: str
    persisted: bool
    intent: str
    complexity: int
    budget_tier: str
    confidence: float
    goal: str = ""
    deliverable: str = ""
    next_action: str = "none"
    constraints: list[str] = Field(default_factory=list)
    do_not: list[str] = Field(default_factory=list)
    stop_when: list[str] = Field(default_factory=list)
    task_contract: dict[str, Any] = Field(default_factory=dict)
    playbook: list[dict[str, Any]] = Field(default_factory=list)
    expected_outcomes: list[dict[str, Any]] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    repeat_until: str = ""
    steps: list[WorkflowStep]
    validation_gates: list[str]
    evidence_requirements: list[str]
    memory_context: list[dict[str, Any]]
    capability_warnings: list[str]
    warnings: list[str] = Field(default_factory=list)


class ProgressResult(BaseModel):
    status: Literal["ok"] = "ok"
    run_id: str
    workflow_status: str
    steps: list[WorkflowStep]
    warnings: list[str] = Field(default_factory=list)


class VerifyResult(BaseModel):
    """Transport result plus an explicit evidence outcome.

    `status=ok` means the MCP call returned normally. `verification_status`
    describes what the check established and must be used for completion gates.
    """

    status: Literal["ok"] = "ok"
    schema_version: str = "1.1"
    check: str
    verification_status: VerificationStatus = VerificationStatus.NOT_CHECKED
    subject_digest: str = ""
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    data: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class MemoryResult(BaseModel):
    status: Literal["ok"] = "ok"
    action: str
    memory_id: int | None = None
    quarantined: bool | None = None
    deleted: bool | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AdminResult(BaseModel):
    status: Literal["ok"] = "ok"
    action: str
    data: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


_PREPARE_ANNOTATIONS = ToolAnnotations(
    title="Prepare task workflow",
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)
_PROGRESS_ANNOTATIONS = ToolAnnotations(
    title="Update workflow progress",
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)
_VERIFY_ANNOTATIONS = ToolAnnotations(
    title="Verify runtime and capabilities",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
_MEMORY_ANNOTATIONS = ToolAnnotations(
    title="Use trusted memory",
    readOnlyHint=False,
    # One action permanently deletes memory; advertise the most conservative
    # tool-level capability to MCP clients that use annotations for consent.
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=False,
)
_ADMIN_ANNOTATIONS = ToolAnnotations(
    title="Inspect Elite MCP runtime",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def _workflow_steps(run: dict[str, Any]) -> list[WorkflowStep]:
    return [
        WorkflowStep(
            index=int(step.get("step_index", index)),
            name=str(step.get("step_name", "unknown")),
            action=str(step.get("action", "")),
            status=str(step.get("status", "pending")),
            evidence=str(step.get("evidence", "")),
        )
        for index, step in enumerate(run.get("steps", []), 1)
    ]


def _checked_result(
    *,
    check: str,
    status: VerificationStatus,
    data: dict[str, Any],
    subject_kind: str,
    subject: str,
    producer: str,
    evidence_payload: dict[str, Any] | None = None,
    limitations: list[str] | None = None,
) -> VerifyResult:
    digest = subject_digest(subject_kind, subject)
    limits = list(limitations or [])
    record = evidence_record(
        kind=check,
        producer=producer,
        subject_digest_value=digest,
        payload=evidence_payload if evidence_payload is not None else data,
        limitations=limits,
    )
    enriched = dict(data)
    enriched.setdefault("verification_status", status.value)
    enriched.setdefault("subject_digest", digest)
    enriched.setdefault("evidence_ids", [record.id])
    return VerifyResult(
        check=check,
        verification_status=status,
        subject_digest=digest,
        evidence=[record],
        limitations=limits,
        data=enriched,
    )


def _persist_checked_result(store, run_id: str, result: VerifyResult) -> VerifyResult:
    if not run_id.strip():
        return result
    if store.get_workflow_run(run_id.strip()) is None:
        raise validation_error("Workflow run was not found.")
    for record in result.evidence:
        payload = record.model_dump(mode="json")
        payload["verification_status"] = result.verification_status.value
        if not store.record_workflow_evidence(run_id.strip(), result.check, payload):
            raise validation_error("Verification evidence could not be persisted for the workflow run.")
    return result


def _gate_outcomes_with_workflow_evidence(
    *,
    data: dict[str, Any],
    contract,
    store,
    run_id: str,
    project_root: str,
) -> dict[str, Any]:
    """Reject code completion when command/scope evidence is missing or stale."""
    if not run_id.strip():
        return data

    from core.verification.git_diff import verify_git_diff

    unmet: list[str] = []
    accepted_ids: list[str] = []
    kinds = {item.kind for item in contract.constraints}
    current_snapshot_digest = ""

    if "run_tests" in kinds:
        test_records = store.list_workflow_evidence(run_id.strip(), check_kind="tests", limit=20)
        passing = next(
            (
                item
                for item in test_records
                if item.get("verification_status") == VerificationStatus.PASS.value
                and isinstance(item.get("payload"), dict)
                and item["payload"].get("executed") is True
            ),
            None,
        )
        if passing is None:
            unmet.append("run_tests: no independently executed passing test evidence is attached to this workflow")
        else:
            expected_snapshot = str(passing["payload"].get("repository_snapshot_digest") or "")
            if not expected_snapshot:
                unmet.append("run_tests: passing test evidence is not bound to a repository snapshot")
            elif not project_root.strip():
                unmet.append("run_tests: project_root is required to prove the tested repository state is still current")
            else:
                snapshot = verify_git_diff(project_root=project_root)
                unavailable = snapshot.status is VerificationStatus.UNKNOWN or (
                    snapshot.status is VerificationStatus.NOT_CHECKED
                    and not snapshot.reason.startswith("no allowed_files policy")
                )
                if unavailable:
                    unmet.append(f"run_tests: current repository state is unavailable ({snapshot.reason})")
                else:
                    current_snapshot_digest = subject_digest("git_worktree_snapshot", snapshot.snapshot_material)
                    if current_snapshot_digest != expected_snapshot:
                        unmet.append("run_tests: repository state changed after the passing test evidence was collected")
                    else:
                        accepted_ids.append(str(passing["id"]))

    scope_constraints = [item for item in contract.constraints if item.kind == "scope_files"]
    if scope_constraints:
        if not project_root.strip():
            unmet.append("scope_files: project_root is required for Git scope verification")
        else:
            allowed = [str(path) for item in scope_constraints for path in item.terms]
            scope_result = verify_git_diff(project_root=project_root, allowed_files=allowed)
            if scope_result.status is not VerificationStatus.PASS:
                unmet.append(f"scope_files: {scope_result.reason}")

    gated = dict(data)
    if unmet:
        gated["passed"] = False
        gated["action"] = "REPEAT"
        gated["unmet"] = list(dict.fromkeys([*gated.get("unmet", []), *unmet]))
        gated["instruction"] = (
            "REPEAT. Do not present a final answer. Collect fresh command and repository evidence, then verify again."
        )
    gated["evidence_gate"] = {
        "passed": not unmet,
        "accepted_evidence_ids": accepted_ids,
        "current_repository_snapshot_digest": current_snapshot_digest,
        "unmet": unmet,
    }
    return gated


def register(mcp, store, profile) -> None:
    """Register the five public v2 gateway tools."""

    @mcp.tool(name="elite_prepare", annotations=_PREPARE_ANNOTATIONS)
    def elite_prepare(
        user_prompt: Annotated[str, Field(min_length=1, max_length=16000)],
        persist: bool = True,
    ) -> PrepareResult:
        """Call first on every non-trivial prompt. Returns the only tools you may use, in order, plus the outcome benchmark. Not the answer."""
        run = build_workflow_run(user_prompt, store=store, persist=persist)
        warnings = []
        if not persist:
            warnings.append("This workflow is not durable; elite_progress cannot update it after this call.")
        contract = dict(run.get("task_contract") or {})
        return PrepareResult(
            run_id=str(run["run_id"]),
            persisted=persist,
            intent=str(run["intent"]),
            complexity=int(run["complexity"]),
            budget_tier=str(run["budget_tier"]),
            confidence=float(run["confidence"]),
            goal=str(run.get("goal") or contract.get("goal") or ""),
            deliverable=str(run.get("deliverable") or contract.get("deliverable") or ""),
            next_action=str(run.get("next_action") or contract.get("next_action") or "none"),
            constraints=[
                f"[{item.get('id', '')}] {item.get('description', '')}" if isinstance(item, dict) else str(item)
                for item in contract.get("constraints", [])
            ],
            do_not=[str(item) for item in contract.get("do_not", [])],
            stop_when=[str(item) for item in contract.get("stop_when", [])],
            task_contract=contract,
            playbook=list(run.get("playbook") or contract.get("playbook") or []),
            expected_outcomes=list(run.get("expected_outcomes") or contract.get("expected_outcomes") or []),
            allowed_tools=[str(item) for item in (run.get("allowed_tools") or contract.get("allowed_tools") or [])],
            repeat_until=str(run.get("repeat_until") or contract.get("repeat_until") or ""),
            steps=_workflow_steps(run),
            validation_gates=[str(item) for item in run.get("validation_gates", [])],
            evidence_requirements=[str(item) for item in run.get("evidence_requirements", [])],
            memory_context=list(run.get("memory_context", [])),
            capability_warnings=[str(item) for item in run.get("capability_warnings", [])],
            warnings=warnings,
        )

    @mcp.tool(name="elite_progress", annotations=_PROGRESS_ANNOTATIONS)
    def elite_progress(
        run_id: Annotated[str, Field(min_length=3, max_length=128)],
        action: Literal["status", "update"] = "status",
        step_index: Annotated[int, Field(ge=0, le=1000)] = 0,
        step_status: Literal["", "pending", "running", "passed", "failed", "skipped", "blocked"] = "",
        evidence: Annotated[str, Field(max_length=2000)] = "",
    ) -> ProgressResult:
        """Read or update durable workflow progress with validation evidence."""
        normalized_action = action.strip().lower()
        if normalized_action == "update":
            allowed_statuses = {"pending", "running", "passed", "failed", "skipped", "blocked"}
            normalized_status = step_status.strip().lower()
            if step_index < 1 or normalized_status not in allowed_statuses:
                raise validation_error(
                    "For action=update, provide step_index >= 1 and a status of pending, running, passed, failed, skipped, or blocked."
                )
            run = store.get_workflow_run(run_id)
            if run is None:
                raise validation_error("Workflow run was not found.")
            selected_step = next((step for step in run["steps"] if step["step_index"] == step_index), None)
            if selected_step is None:
                raise validation_error("Workflow step was not found.")
            terminal_statuses = {"passed", "failed", "skipped", "blocked"}
            if normalized_status in terminal_statuses and not evidence.strip():
                raise validation_error("Terminal workflow updates require concise evidence or a blocker rationale.")
            if normalized_status in {"passed", "skipped"}:
                unfinished = [
                    step["step_index"]
                    for step in run["steps"]
                    if step["step_index"] < step_index and step["status"] not in {"passed", "skipped"}
                ]
                if unfinished:
                    raise validation_error(
                        "Complete or explicitly skip earlier workflow steps before marking this step complete: "
                        + ", ".join(str(index) for index in unfinished)
                    )
            if not store.update_workflow_step(run_id, step_index, normalized_status, evidence):
                raise validation_error("Workflow step was not found.")
        elif normalized_action != "status":
            raise validation_error("action must be status or update.")

        run = store.get_workflow_run(run_id)
        if run is None:
            raise validation_error("Workflow run was not found.")
        return ProgressResult(
            run_id=run_id,
            workflow_status=str(run.get("status", "planned")),
            steps=_workflow_steps(run),
        )

    @mcp.tool(name="elite_verify", annotations=_VERIFY_ANNOTATIONS)
    async def elite_verify(
        check: Literal[
            "doctor",
            "capabilities",
            "constraints",
            "evidence",
            "syntax",
            "tests",
            "grounding",
            "outcomes",
            "diff",
        ] = "doctor",
        query: Annotated[str, Field(max_length=2000)] = "",
        draft: Annotated[str, Field(max_length=20000)] = "",
        run_id: Annotated[str, Field(max_length=128)] = "",
        code: Annotated[str, Field(max_length=20000)] = "",
        language: Annotated[str, Field(max_length=32)] = "python",
        command: Annotated[str, Field(max_length=400)] = "",
        project_root: Annotated[str, Field(max_length=1024)] = "",
        allowed_files: Annotated[list[str] | None, Field(max_length=100)] = None,
        forbid_dependency_changes: bool = False,
    ) -> VerifyResult:
        """Verify health, constraints, syntax, tests, Git scope, outcomes, or grounded evidence."""
        normalized_check = check.strip().lower()
        if normalized_check == "doctor":
            return VerifyResult(check="doctor", data=build_doctor_report(store, profile=profile, mcp=mcp))
        if normalized_check == "capabilities":
            registry = build_capability_registry()
            return VerifyResult(
                check="capabilities",
                data={
                    "active_ide": registry.active_ide,
                    "warnings": list(registry.warnings),
                    "mcps": [cap.name for cap in registry.by_kind("mcp", recommendable_only=False)],
                    "skills": [cap.name for cap in registry.by_kind("skill", recommendable_only=False)],
                },
            )
        if normalized_check in {"constraints", "outcomes"}:
            from core.reasoning.constraint_check import check_draft
            from core.reasoning.playbook import verify_outcomes
            from core.reasoning.task_contract import compile_task_contract, contract_from_dict

            contract = None
            if run_id.strip():
                run = store.get_workflow_run(run_id.strip())
                if run is None:
                    raise validation_error("Workflow run was not found.")
                raw = run.get("task_contract") or {}
                stored = raw if isinstance(raw, dict) else {}
                fallback = query or draft or str(stored.get("goal") or "task")
                contract = contract_from_dict(stored, fallback)
            if contract is None:
                if not (query or draft):
                    raise validation_error(f"{normalized_check} check needs draft or run_id.")
                contract = compile_task_contract(query or draft)
            if normalized_check == "outcomes":
                if not draft.strip():
                    raise validation_error("outcomes check needs draft.")
                data = verify_outcomes(draft, contract)
                data = _gate_outcomes_with_workflow_evidence(
                    data=data,
                    contract=contract,
                    store=store,
                    run_id=run_id,
                    project_root=project_root,
                )
                checked = _checked_result(
                    check="outcomes",
                    status=status_from_bool(bool(data["passed"])),
                    data=data,
                    subject_kind="draft",
                    subject=draft,
                    producer="core.reasoning.playbook.verify_outcomes",
                    evidence_payload={
                        "passed": bool(data["passed"]),
                        "action": str(data["action"]),
                        "unmet": list(data["unmet"]),
                        "evidence_gate": dict(data.get("evidence_gate") or {}),
                    },
                    limitations=[
                        "Draft checks do not prove repository state, command execution, or runtime behavior."
                    ],
                )
                return _persist_checked_result(store, run_id, checked)
            report = check_draft(draft, contract)
            return _checked_result(
                check="constraints",
                status=status_from_bool(report.passed),
                data=report.to_dict(),
                subject_kind="draft",
                subject=draft,
                producer="core.reasoning.constraint_check.check_draft",
                evidence_payload={"passed": report.passed, "unmet": list(report.unmet)},
                limitations=["Lexical and format constraints inspect only the supplied draft."],
            )
        if normalized_check == "evidence":
            from core.evidence.grounded_search import grounded_evidence

            if not query.strip():
                raise validation_error("query is required for check=evidence.")
            evidence = await grounded_evidence(query.strip())
            data = evidence.to_dict()
            evidence_status = (
                VerificationStatus.PASS if evidence.quotes and not evidence.degraded else VerificationStatus.UNKNOWN
            )
            limitations = list(evidence.uncertain)
            if evidence.degraded:
                limitations.append("Retrieval is degraded; evidence coverage is incomplete.")
            return _checked_result(
                check="evidence",
                status=evidence_status,
                data=data,
                subject_kind="query",
                subject=query.strip(),
                producer="core.evidence.grounded_search.grounded_evidence",
                evidence_payload={
                    "sources_fetched": evidence.sources_fetched,
                    "sources_readable": evidence.sources_readable,
                    "quote_count": len(evidence.quotes),
                    "degraded": evidence.degraded,
                    "retrieved_at": evidence.retrieved_at,
                },
                limitations=list(dict.fromkeys(limitations)),
            )
        if normalized_check == "syntax":
            from core.cognitive.leverage.deterministic_gates import validate_syntax

            target = code or draft
            if not target.strip():
                raise validation_error("code or draft is required for check=syntax.")
            result = validate_syntax(target, language or "python")
            data = result.to_dict()
            return _checked_result(
                check="syntax",
                status=status_from_bool(bool(data.get("passed"))),
                data=data,
                subject_kind=f"source:{language or 'python'}",
                subject=target,
                producer="core.cognitive.leverage.deterministic_gates.validate_syntax",
                limitations=["Syntax and selected static rules do not prove runtime correctness or security."],
            )
        if normalized_check == "tests":
            from core.verification.git_diff import verify_git_diff

            execution_root = ""
            repository_limitation = ""
            if project_root.strip():
                discovered = verify_git_diff(project_root=project_root)
                unavailable = discovered.status is VerificationStatus.UNKNOWN or (
                    discovered.status is VerificationStatus.NOT_CHECKED
                    and not discovered.reason.startswith("no allowed_files policy")
                )
                if unavailable:
                    data = {
                        "passed": False,
                        "executed": False,
                        "reason": f"project_root is unavailable: {discovered.reason}",
                        "command": command.strip(),
                    }
                    repository_limitation = discovered.reason
                else:
                    execution_root = discovered.repository_root
                    data = _run_allowlisted_command(command, cwd=execution_root)
            else:
                data = _run_allowlisted_command(command)
            if data.get("executed"):
                test_status = status_from_bool(bool(data.get("passed")))
            elif str(data.get("reason", "")).startswith("set ELITE_ALLOW_TEST_COMMAND") or "allowlist" in str(
                data.get("reason", "")
            ):
                test_status = VerificationStatus.NOT_CHECKED
            else:
                test_status = VerificationStatus.UNKNOWN
            repository_snapshot_digest = ""
            if project_root.strip() and execution_root:
                snapshot = verify_git_diff(project_root=execution_root)
                unavailable = snapshot.status is VerificationStatus.UNKNOWN or (
                    snapshot.status is VerificationStatus.NOT_CHECKED
                    and not snapshot.reason.startswith("no allowed_files policy")
                )
                if unavailable:
                    repository_limitation = snapshot.reason
                else:
                    repository_snapshot_digest = subject_digest(
                        "git_worktree_snapshot", snapshot.snapshot_material
                    )
            data["repository_snapshot_digest"] = repository_snapshot_digest
            checked = _checked_result(
                check="tests",
                status=test_status,
                data=data,
                subject_kind="test_command_and_repository",
                subject=f"{command.strip()}\0{repository_snapshot_digest}",
                producer="core.tools.gateway._run_allowlisted_command",
                evidence_payload={
                    "command": data.get("command", command.strip()),
                    "executed": bool(data.get("executed")),
                    "returncode": data.get("returncode"),
                    "passed": bool(data.get("passed")),
                    "reason": data.get("reason", ""),
                    "repository_snapshot_digest": repository_snapshot_digest,
                },
                limitations=[
                    item
                    for item in (
                        "" if data.get("executed") else str(data.get("reason") or "Command was not executed."),
                        repository_limitation,
                        "" if project_root.strip() else "No project_root was supplied; test evidence is not bound to repository state.",
                    )
                    if item
                ],
            )
            return _persist_checked_result(store, run_id, checked)
        if normalized_check == "diff":
            from core.verification.git_diff import verify_git_diff

            scope = list(allowed_files or [])
            if run_id.strip():
                run = store.get_workflow_run(run_id.strip())
                if run is None:
                    raise validation_error("Workflow run was not found.")
                raw_contract = run.get("task_contract") or {}
                if isinstance(raw_contract, dict):
                    for item in raw_contract.get("constraints") or []:
                        if isinstance(item, dict) and item.get("kind") == "scope_files":
                            for path in item.get("terms") or []:
                                if str(path) not in scope:
                                    scope.append(str(path))
            result = verify_git_diff(
                project_root=project_root,
                allowed_files=scope,
                forbid_dependency_changes=forbid_dependency_changes,
            )
            data = result.to_dict()
            checked = _checked_result(
                check="diff",
                status=result.status,
                data=data,
                subject_kind="git_worktree_snapshot",
                subject=result.snapshot_material,
                producer="core.verification.git_diff.verify_git_diff",
                evidence_payload={
                    "repository_root": result.repository_root,
                    "changed_files": [item.to_dict() for item in result.changed_files],
                    "allowed_files": list(result.allowed_files),
                    "out_of_scope": list(result.out_of_scope),
                    "dependency_changes": list(result.dependency_changes),
                    "reason": result.reason,
                },
                limitations=(
                    []
                    if result.status in {VerificationStatus.PASS, VerificationStatus.FAIL}
                    else [result.reason]
                ),
            )
            return _persist_checked_result(store, run_id, checked)
        if normalized_check == "grounding":
            from core.evidence.grounded_search import grounded_evidence, grounding_check

            if not draft.strip() or not query.strip():
                raise validation_error("grounding check needs query and draft.")

            evidence = await grounded_evidence(query.strip())
            report = grounding_check(draft, evidence)
            report["evidence"] = evidence.to_dict()
            definitive_failure = bool(report.get("hallucinated_urls") or report.get("unsupported_quotes"))
            if definitive_failure:
                grounding_status = VerificationStatus.FAIL
            elif evidence.degraded:
                grounding_status = VerificationStatus.UNKNOWN
            else:
                grounding_status = status_from_bool(bool(report.get("passed")))
            limitations = list(evidence.uncertain)
            if evidence.degraded:
                limitations.append("Grounding coverage is incomplete because retrieval is degraded.")
            return _checked_result(
                check="grounding",
                status=grounding_status,
                data=report,
                subject_kind="grounding_draft",
                subject=f"{query.strip()}\0{draft}",
                producer="core.evidence.grounded_search.grounding_check",
                evidence_payload={
                    "passed": bool(report.get("passed")),
                    "hallucinated_urls": list(report.get("hallucinated_urls") or []),
                    "unsupported_quotes": list(report.get("unsupported_quotes") or []),
                    "degraded": evidence.degraded,
                    "quote_count": len(evidence.quotes),
                },
                limitations=list(dict.fromkeys(limitations)),
            )
        raise validation_error(
            "check must be doctor, capabilities, constraints, evidence, syntax, tests, diff, grounding, or outcomes."
        )

    @mcp.tool(name="elite_memory", annotations=_MEMORY_ANNOTATIONS)
    def elite_memory(
        action: Literal["search", "remember", "approve", "forget"] = "search",
        query: Annotated[str, Field(max_length=2000)] = "",
        content: Annotated[str, Field(max_length=5000)] = "",
        memory_type: Annotated[str, Field(min_length=1, max_length=80)] = "fact",
        scope: Annotated[str, Field(min_length=1, max_length=128)] = "global",
        memory_id: Annotated[int, Field(ge=0)] = 0,
        trust_score: Annotated[float, Field(ge=0.0, le=1.0)] = 0.7,
        privacy_class: Annotated[str, Field(min_length=1, max_length=64)] = "internal",
        confirm: bool = False,
    ) -> MemoryResult:
        """Search, record, or explicitly approve scoped memory items."""
        normalized_action = action.strip().lower()
        if normalized_action == "search":
            return MemoryResult(
                action="search",
                items=store.search_memory_items(query=query, scope=scope, limit=8, min_trust=0.5),
            )
        if normalized_action == "remember":
            if not content.strip():
                raise validation_error("content is required for action=remember.")
            item_id = store.record_memory_item(
                memory_type=memory_type,
                content=content,
                scope=scope,
                source="explicit_gateway",
                trust_score=trust_score,
                privacy_class=privacy_class,
            )
            item = store.get_memory_item(item_id, include_quarantined=True)
            quarantined = bool(item and item.get("quarantined"))
            return MemoryResult(
                action="remember",
                memory_id=item_id,
                quarantined=quarantined,
                items=[item] if item else [],
            )
        if normalized_action == "approve":
            if memory_id < 1:
                raise validation_error("memory_id is required for action=approve.")
            if not store.approve_memory_item(memory_id, trust_score=trust_score):
                raise validation_error(f"Quarantined memory item `{memory_id}` was not found.")
            item = store.get_memory_item(memory_id, include_quarantined=True)
            return MemoryResult(
                action="approve",
                memory_id=memory_id,
                quarantined=False,
                items=[item] if item else [],
            )
        if normalized_action == "forget":
            if memory_id < 1:
                raise validation_error("memory_id is required for action=forget.")
            if not confirm:
                raise validation_error("action=forget permanently deletes memory; re-run with confirm=true.")
            if not store.delete_memory_item(memory_id):
                raise validation_error(f"Memory item `{memory_id}` was not found.")
            return MemoryResult(action="forget", memory_id=memory_id, deleted=True)
        raise validation_error("action must be search, remember, approve, or forget.")

    @mcp.tool(name="elite_admin", annotations=_ADMIN_ANNOTATIONS)
    def elite_admin(action: Literal["status", "privacy", "monitoring"] = "status") -> AdminResult:
        """Inspect runtime identity, privacy policy, or active server profile."""
        normalized_action = action.strip().lower()
        if normalized_action == "status":
            return AdminResult(
                action="status",
                data={
                    "runtime": runtime_identity(),
                    "tool_profile": getattr(mcp, "_elite_tool_profile", "unknown"),
                    "active_ide": profile.ide_type,
                    "sync_enabled": profile.sync_enabled,
                },
            )
        if normalized_action == "privacy":
            from core.privacy import raw_prompt_storage_enabled, telemetry_mode

            return AdminResult(
                action="privacy",
                data={
                    "telemetry_mode": telemetry_mode(),
                    "raw_prompt_storage_enabled": raw_prompt_storage_enabled(),
                    "sync_requires_confirm": True,
                },
            )
        if normalized_action == "monitoring":
            return AdminResult(
                action="monitoring",
                data={
                    "local_only": True,
                    "operational_summary": store.get_operational_summary(days=7),
                    "tool_usage": store.get_tool_usage_stats(days=7),
                },
            )
        raise validation_error("action must be status, privacy, or monitoring.")
