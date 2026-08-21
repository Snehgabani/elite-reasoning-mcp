"""Compact, typed v2 MCP gateway tools.

The default profile intentionally exposes a small task-oriented surface. The
legacy profile keeps the individual tools available for established clients.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.types import ToolAnnotations
from pydantic import Field

from core.api.schemas import AdminResult, MemoryResult, PrepareResult, ProgressResult, VerifyResult, WorkflowStep
from core.orchestration.capabilities import build_capability_registry
from core.orchestration.continuity import next_continuation
from core.orchestration.workflow_run import build_workflow_run
from core.runtime import runtime_identity
from core.tools.doctor import build_doctor_report
from core.tools.errors import validation_error
from core.verification.models import VerificationStatus, evidence_record, subject_digest
from core.verification.registry import VerificationInputError, VerifierRequest, build_core_verifier_registry


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


def register(mcp, store, profile) -> None:
    """Register the five public v2 gateway tools and continuity prompt."""
    verifier_registry = build_core_verifier_registry(store)

    @mcp.prompt(name="goal")
    def goal_prompt(objective: str) -> str:
        """Anchor a durable goal and continuous verification lifecycle."""
        return (
            f"GOAL: {objective}\n\n"
            "Start by calling elite_prepare with this exact goal and persist=true. Retain run_id. "
            "After every Elite response inspect continuation. If stop_final_response=true, call required_tool "
            "with required_args before answering. Continue until checkpoint=done. If context becomes long or "
            "you are unsure what comes next, call elite_progress(action='status', run_id=<saved run_id>)."
        )

    @mcp.tool(name="elite_prepare", annotations=_PREPARE_ANNOTATIONS)
    def elite_prepare(
        user_prompt: Annotated[str, Field(min_length=1, max_length=16000)],
        persist: bool = True,
    ) -> PrepareResult:
        """Start a non-trivial task. Retain run_id and obey the returned continuation after each later Elite call. Not the answer."""
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
            continuation=(
                next_continuation(store, str(run["run_id"])).to_dict()
                if persist
                else {
                    "run_id": str(run["run_id"]),
                    "phase": "EPHEMERAL",
                    "checkpoint": "verify_outcomes",
                    "required_tool": "elite_verify",
                    "required_args": {"check": "outcomes", "draft": "<final draft>", "query": user_prompt},
                    "instruction": "This run is not durable. Verify the final draft directly before answering.",
                    "stop_final_response": True,
                }
            ),
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
        """Resume durable state after context dilution; returns the exact next required checkpoint in continuation."""
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
            continuation=next_continuation(store, run_id).to_dict(),
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
            "cegis",
            "diagnostics",
            "types",
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
        """Run one check, persist evidence by run_id, then follow the returned continuation before answering."""
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
        if verifier_registry.supports(normalized_check):
            request = VerifierRequest(
                check=normalized_check,
                query=query,
                draft=draft,
                run_id=run_id,
                code=code,
                language=language,
                command=command,
                project_root=project_root,
                allowed_files=tuple(allowed_files or ()),
                forbid_dependency_changes=forbid_dependency_changes,
            )
            try:
                execution = await verifier_registry.verify(request)
            except VerificationInputError as exc:
                raise validation_error(str(exc)) from exc
            checked = _checked_result(
                check=execution.check,
                status=execution.status,
                data=execution.data,
                subject_kind=execution.subject_kind,
                subject=execution.subject,
                producer=execution.producer,
                evidence_payload=execution.evidence_payload,
                limitations=list(execution.limitations),
            )
            checked = _persist_checked_result(store, run_id, checked)
            if run_id.strip():
                checked.continuation = next_continuation(store, run_id.strip()).to_dict()
                checked.data["continuation"] = checked.continuation
            return checked
        supported = ", ".join(("doctor", "capabilities", *verifier_registry.names()))
        raise validation_error(f"unsupported check; choose one of: {supported}.")

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
