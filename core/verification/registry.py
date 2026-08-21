"""Typed verifier registry and core verifier implementations.

The MCP gateway adapts transport parameters into a `VerifierRequest`; it does
not decide verification semantics. This keeps each check independently
falsifiable and makes the set of supported checks inspectable.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Protocol

from core.contracts.models import Requirement, RequirementKind
from core.verification.models import Evidence, VerificationResult

from core.verification.command import CommandInputError, run_allowlisted_command
from core.verification.git_diff import verify_git_diff
from core.verification.models import VerificationStatus, status_from_bool, subject_digest


class VerificationInputError(ValueError):
    """A caller-correctable verifier request error."""


@dataclass(frozen=True)
class VerifierRequest:
    check: str
    query: str = ""
    draft: str = ""
    run_id: str = ""
    code: str = ""
    language: str = "python"
    command: str = ""
    project_root: str = ""
    allowed_files: tuple[str, ...] = ()
    forbid_dependency_changes: bool = False


@dataclass(frozen=True)
class VerificationExecution:
    check: str
    status: VerificationStatus
    data: dict[str, Any]
    subject_kind: str
    subject: str
    producer: str
    evidence_payload: dict[str, Any]
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerifierContext:
    store: Any


class Verifier(Protocol):
    name: str

    async def verify(self, request: VerifierRequest, context: VerifierContext) -> VerificationExecution: ...


class VerifierRegistry:
    def __init__(self, context: VerifierContext | None = None, register_builtins: bool = True):
        self._context = context or VerifierContext(store=None)
        self._verifiers: dict[str, Any] = {}
        self._kind_mapping: dict[RequirementKind, str] = {}
        self._builtins_loaded = not register_builtins

    def _ensure_builtins(self) -> None:
        if self._builtins_loaded:
            return
        self._builtins_loaded = True
        from core.verification.cegis import CEGISPropertyVerifier
        from core.verification.completeness import EvidenceCompletenessVerifier
        from core.verification.constraints import ConstraintVerifier as RequirementConstraintVerifier
        from core.verification.git_diff import GitDiffScopeVerifier
        from core.verification.syntax import PythonSyntaxVerifier
        from core.verification.test_command import TestCommandVerifier as RequirementTestCommandVerifier
        from core.verification.type_checker import TypeInvariantVerifier

        for verifier in (
            RequirementConstraintVerifier(),
            PythonSyntaxVerifier(),
            RequirementTestCommandVerifier(),
            GitDiffScopeVerifier(),
            EvidenceCompletenessVerifier(),
            CEGISPropertyVerifier(),
            TypeInvariantVerifier(),
        ):
            self.register(verifier, allow_replace=True)

    def register(
        self,
        verifier: Any,
        default_for_kinds: list[RequirementKind] | None = None,
        *,
        allow_replace: bool = False,
    ) -> None:
        name = verifier.name.strip().lower()
        if not name:
            raise ValueError("verifier name is required")
        if name in self._verifiers and not allow_replace:
            raise ValueError(f"verifier already registered: {name}")
        self._verifiers[name] = verifier
        kinds = default_for_kinds if default_for_kinds is not None else getattr(verifier, "supported_requirement_kinds", ())
        for kind in kinds:
            self._kind_mapping.setdefault(kind, name)

    def get(self, name: str) -> Any | None:
        self._ensure_builtins()
        return self._verifiers.get(name.strip().lower())

    def get_for_kind(self, kind: RequirementKind) -> Any | None:
        self._ensure_builtins()
        name = self._kind_mapping.get(kind)
        return self._verifiers.get(name) if name else None

    def verify_requirement(
        self,
        requirement: Requirement,
        subject_content: str,
        evidence_records: list[Evidence] | None = None,
    ) -> VerificationResult:
        started = time.perf_counter()
        verifier = self.get(requirement.verifier) if requirement.verifier else self.get_for_kind(requirement.kind)
        if verifier is None:
            return VerificationResult(
                requirement_id=requirement.id,
                verifier="unregistered",
                status=VerificationStatus.NOT_CHECKED,
                reason=f"No matching verifier registered for requirement kind: {requirement.kind.value}",
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
            )
        try:
            result = verifier.verify(requirement, subject_content, evidence_records)
            result.duration_ms = round((time.perf_counter() - started) * 1000, 3)
            return result
        except Exception as exc:
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=verifier.name,
                verifier_version=getattr(verifier, "version", "1.0.0"),
                status=VerificationStatus.UNKNOWN,
                reason=f"Verifier execution error: {type(exc).__name__}: {exc}",
                limitations=["Unhandled runtime exception during verification"],
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
            )

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._verifiers))

    def supports(self, name: str) -> bool:
        return name.strip().lower() in self._verifiers

    async def verify(self, request: VerifierRequest) -> VerificationExecution:
        name = request.check.strip().lower()
        verifier = self._verifiers.get(name)
        if verifier is None:
            raise VerificationInputError(f"unsupported verification check: {name}")
        return await verifier.verify(request, self._context)


def _resolve_contract(request: VerifierRequest, store: Any):
    from core.reasoning.task_contract import compile_task_contract, contract_from_dict

    if request.run_id.strip():
        run = store.get_workflow_run(request.run_id.strip())
        if run is None:
            raise VerificationInputError("Workflow run was not found.")
        raw = run.get("task_contract") or {}
        stored = raw if isinstance(raw, dict) else {}
        fallback = request.query or request.draft or str(stored.get("goal") or "task")
        return contract_from_dict(stored, fallback)
    if not (request.query or request.draft):
        raise VerificationInputError(f"{request.check} check needs draft or run_id.")
    return compile_task_contract(request.query or request.draft)


def _repository_snapshot(project_root: str) -> tuple[str, str, str]:
    """Return approved root, snapshot digest, or a limitation."""
    if not project_root.strip():
        return "", "", "No project_root was supplied; evidence is not bound to repository state."
    snapshot = verify_git_diff(project_root=project_root)
    unavailable = snapshot.status is VerificationStatus.UNKNOWN or (
        snapshot.status is VerificationStatus.NOT_CHECKED and not snapshot.reason.startswith("no allowed_files policy")
    )
    if unavailable:
        return "", "", snapshot.reason
    return snapshot.repository_root, subject_digest("git_worktree_snapshot", snapshot.snapshot_material), ""


def _gate_outcomes(
    *, data: dict[str, Any], contract: Any, store: Any, run_id: str, project_root: str
) -> dict[str, Any]:
    """Reject code completion when command/scope evidence is missing or stale."""
    if not run_id.strip():
        return data

    unmet: list[str] = []
    accepted_ids: list[str] = []
    kinds = {item.kind for item in contract.constraints}
    deliverable = str(getattr(contract, "deliverable", "")).lower()
    is_code = bool(kinds & {"run_tests", "scope_files"}) or any(
        term in deliverable for term in ("patch", "code", "validation log")
    )
    current_snapshot_digest = ""

    if is_code:
        syntax_records = store.list_workflow_evidence(run_id.strip(), check_kind="syntax", limit=20)
        syntax = next((item for item in syntax_records if item.get("verification_status") == "PASS"), None)
        if syntax is None:
            unmet.append("syntax: no passing mid-work syntax evidence is attached to this workflow")
        elif project_root.strip():
            expected_syntax_snapshot = str((syntax.get("payload") or {}).get("repository_snapshot_digest") or "")
            if expected_syntax_snapshot:
                _, current_syntax_snapshot, limitation = _repository_snapshot(project_root)
                if limitation or current_syntax_snapshot != expected_syntax_snapshot:
                    unmet.append("syntax: repository state changed after syntax verification")
            else:
                unmet.append("syntax: evidence is not bound to a repository snapshot")

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
                _, current_snapshot_digest, limitation = _repository_snapshot(project_root)
                if limitation:
                    unmet.append(f"run_tests: current repository state is unavailable ({limitation})")
                elif current_snapshot_digest != expected_snapshot:
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
            diff_records = store.list_workflow_evidence(run_id.strip(), check_kind="diff", limit=20)
            diff_evidence = next((item for item in diff_records if item.get("verification_status") == "PASS"), None)
            current_diff_digest = subject_digest("git_worktree_snapshot", scope_result.snapshot_material)
            if diff_evidence is None:
                unmet.append("scope_files: no passing mid-work Git scope evidence is attached to this workflow")
            elif diff_evidence.get("subject_digest") != current_diff_digest:
                unmet.append("scope_files: repository state changed after Git scope verification")

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


class ConstraintVerifier:
    name = "constraints"

    async def verify(self, request: VerifierRequest, context: VerifierContext) -> VerificationExecution:
        from core.reasoning.constraint_check import check_draft

        contract = _resolve_contract(request, context.store)
        report = check_draft(request.draft, contract)
        data = report.to_dict()
        return VerificationExecution(
            check=self.name,
            status=status_from_bool(report.passed),
            data=data,
            subject_kind="draft",
            subject=request.draft,
            producer="core.reasoning.constraint_check.check_draft",
            evidence_payload={"passed": report.passed, "unmet": list(report.unmet)},
            limitations=("Lexical and format constraints inspect only the supplied draft.",),
        )


class OutcomeVerifier:
    name = "outcomes"

    async def verify(self, request: VerifierRequest, context: VerifierContext) -> VerificationExecution:
        from core.reasoning.playbook import verify_outcomes

        if not request.draft.strip():
            raise VerificationInputError("outcomes check needs draft.")
        contract = _resolve_contract(request, context.store)
        data = verify_outcomes(request.draft, contract)
        data = _gate_outcomes(
            data=data,
            contract=contract,
            store=context.store,
            run_id=request.run_id,
            project_root=request.project_root,
        )
        return VerificationExecution(
            check=self.name,
            status=status_from_bool(bool(data["passed"])),
            data=data,
            subject_kind="draft",
            subject=request.draft,
            producer="core.reasoning.playbook.verify_outcomes",
            evidence_payload={
                "passed": bool(data["passed"]),
                "action": str(data["action"]),
                "unmet": list(data["unmet"]),
                "evidence_gate": dict(data.get("evidence_gate") or {}),
            },
            limitations=("Draft checks do not prove repository state beyond attached evidence.",),
        )


class EvidenceVerifier:
    name = "evidence"

    async def verify(self, request: VerifierRequest, context: VerifierContext) -> VerificationExecution:
        from core.evidence.grounded_search import grounded_evidence

        if not request.query.strip():
            raise VerificationInputError("query is required for check=evidence.")
        evidence = await grounded_evidence(request.query.strip())
        data = evidence.to_dict()
        status = VerificationStatus.PASS if evidence.quotes and not evidence.degraded else VerificationStatus.UNKNOWN
        limitations = list(evidence.uncertain)
        if evidence.degraded:
            limitations.append("Retrieval is degraded; evidence coverage is incomplete.")
        return VerificationExecution(
            check=self.name,
            status=status,
            data=data,
            subject_kind="query",
            subject=request.query.strip(),
            producer="core.evidence.grounded_search.grounded_evidence",
            evidence_payload={
                "sources_fetched": evidence.sources_fetched,
                "sources_readable": evidence.sources_readable,
                "quote_count": len(evidence.quotes),
                "degraded": evidence.degraded,
                "retrieved_at": evidence.retrieved_at,
            },
            limitations=tuple(dict.fromkeys(limitations)),
        )


class SyntaxVerifier:
    name = "syntax"

    async def verify(self, request: VerifierRequest, context: VerifierContext) -> VerificationExecution:
        from core.cognitive.leverage.deterministic_gates import validate_syntax

        target = request.code or request.draft
        if not target.strip():
            raise VerificationInputError("code or draft is required for check=syntax.")
        result = validate_syntax(target, request.language or "python")
        data = result.to_dict()
        _, repository_snapshot_digest, repository_limitation = _repository_snapshot(request.project_root)
        data["repository_snapshot_digest"] = repository_snapshot_digest
        return VerificationExecution(
            check=self.name,
            status=status_from_bool(bool(data.get("passed"))),
            data=data,
            subject_kind=f"source:{request.language or 'python'}",
            subject=f"{target}\0{repository_snapshot_digest}",
            producer="core.cognitive.leverage.deterministic_gates.validate_syntax",
            evidence_payload={
                "passed": bool(data.get("passed")),
                "issues": list(data.get("issues") or []),
                "repository_snapshot_digest": repository_snapshot_digest,
            },
            limitations=tuple(
                item
                for item in (
                    "Syntax and selected static rules do not prove runtime correctness or security.",
                    repository_limitation,
                )
                if item
            ),
        )


class TestCommandVerifier:
    name = "tests"

    async def verify(self, request: VerifierRequest, context: VerifierContext) -> VerificationExecution:
        execution_root, _, repository_limitation = _repository_snapshot(request.project_root)
        if request.project_root.strip() and not execution_root:
            data = {
                "passed": False,
                "executed": False,
                "reason": f"project_root is unavailable: {repository_limitation}",
                "command": request.command.strip(),
            }
        else:
            try:
                data = run_allowlisted_command(request.command, cwd=execution_root)
            except CommandInputError as exc:
                raise VerificationInputError(str(exc)) from exc

        if data.get("executed"):
            status = status_from_bool(bool(data.get("passed")))
        elif str(data.get("reason", "")).startswith("set ELITE_ALLOW_TEST_COMMAND") or "allowlist" in str(
            data.get("reason", "")
        ):
            status = VerificationStatus.NOT_CHECKED
        else:
            status = VerificationStatus.UNKNOWN

        repository_snapshot_digest = ""
        if execution_root:
            _, repository_snapshot_digest, post_limitation = _repository_snapshot(execution_root)
            repository_limitation = post_limitation or repository_limitation
        data["repository_snapshot_digest"] = repository_snapshot_digest
        limitations = [
            item
            for item in (
                "" if data.get("executed") else str(data.get("reason") or "Command was not executed."),
                repository_limitation,
            )
            if item
        ]
        return VerificationExecution(
            check=self.name,
            status=status,
            data=data,
            subject_kind="test_command_and_repository",
            subject=f"{request.command.strip()}\0{repository_snapshot_digest}",
            producer="core.verification.command.run_allowlisted_command",
            evidence_payload={
                "command": data.get("command", request.command.strip()),
                "executed": bool(data.get("executed")),
                "returncode": data.get("returncode"),
                "passed": bool(data.get("passed")),
                "reason": data.get("reason", ""),
                "repository_snapshot_digest": repository_snapshot_digest,
            },
            limitations=tuple(limitations),
        )


class GitDiffVerifier:
    name = "diff"

    async def verify(self, request: VerifierRequest, context: VerifierContext) -> VerificationExecution:
        scope = list(request.allowed_files)
        if request.run_id.strip():
            run = context.store.get_workflow_run(request.run_id.strip())
            if run is None:
                raise VerificationInputError("Workflow run was not found.")
            raw_contract = run.get("task_contract") or {}
            if isinstance(raw_contract, dict):
                for item in raw_contract.get("constraints") or []:
                    if isinstance(item, dict) and item.get("kind") == "scope_files":
                        for path in item.get("terms") or []:
                            if str(path) not in scope:
                                scope.append(str(path))
        result = verify_git_diff(
            project_root=request.project_root,
            allowed_files=scope,
            forbid_dependency_changes=request.forbid_dependency_changes,
        )
        data = result.to_dict()
        return VerificationExecution(
            check=self.name,
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
                "snapshot_errors": list(result.snapshot_errors),
                "reason": result.reason,
            },
            limitations=(
                () if result.status in {VerificationStatus.PASS, VerificationStatus.FAIL} else (result.reason,)
            ),
        )


class CegisVerifier:
    name = "cegis"

    async def verify(self, request: VerifierRequest, context: VerifierContext) -> VerificationExecution:
        from core.contracts.models import RequirementSeverity
        from core.verification.cegis import CEGISPropertyVerifier

        if not request.code.strip():
            raise VerificationInputError("code is required for check=cegis.")
        requirement = Requirement(
            id="cegis",
            kind=RequirementKind.ROBUSTNESS,
            source_text="",
            interpretation="Check boundary resilience",
            severity=RequirementSeverity.REQUIRED,
        )
        result = CEGISPropertyVerifier().verify(requirement, request.code)
        data = result.model_dump(mode="json")
        data["status"] = result.status.value
        return VerificationExecution(
            check=self.name,
            status=result.status,
            data=data,
            subject_kind="source:python",
            subject=request.code,
            producer="core.verification.cegis.CEGISPropertyVerifier",
            evidence_payload={"status": result.status.value, "reason": result.reason},
            limitations=tuple(result.limitations),
        )


class TypeVerifier:
    name = "types"

    async def verify(self, request: VerifierRequest, context: VerifierContext) -> VerificationExecution:
        from core.verification.type_checker import TypeInvariantVerifier

        if not request.code.strip():
            raise VerificationInputError("code is required for check=types.")
        requirement = Requirement(
            id="types",
            kind=RequirementKind.COMPATIBILITY,
            source_text="",
            interpretation="Check public return annotations",
        )
        result = TypeInvariantVerifier().verify(requirement, request.code)
        data = result.model_dump(mode="json")
        data["status"] = result.status.value
        return VerificationExecution(
            check=self.name,
            status=result.status,
            data=data,
            subject_kind="source:python",
            subject=request.code,
            producer="core.verification.type_checker.TypeInvariantVerifier",
            evidence_payload={"status": result.status.value, "reason": result.reason},
            limitations=tuple(result.limitations),
        )


class DiagnosticVerifier:
    name = "diagnostics"

    async def verify(self, request: VerifierRequest, context: VerifierContext) -> VerificationExecution:
        from core.verification.diagnostics import extract_diagnostic_slice

        if not request.query.strip():
            raise VerificationInputError("query traceback is required for check=diagnostics.")
        diagnostic = extract_diagnostic_slice(request.query, source_code=request.code or None)
        data = diagnostic.model_dump(mode="json")
        return VerificationExecution(
            check=self.name,
            status=VerificationStatus.NOT_CHECKED,
            data=data,
            subject_kind="diagnostic_input",
            subject=f"{request.query}\0{request.code}",
            producer="core.verification.diagnostics.extract_diagnostic_slice",
            evidence_payload={"error_type": diagnostic.error_type, "failing_line_number": diagnostic.failing_line_number},
            limitations=("Diagnostic slicing structures an error; it does not verify a repair.",),
        )


class SymbolOutlineVerifier:
    name = "outline"

    async def verify(self, request: VerifierRequest, context: VerifierContext) -> VerificationExecution:
        from core.search.symbol_indexer import extract_symbol_outline

        target = request.code or request.draft
        if not target.strip():
            raise VerificationInputError("code or draft is required for check=outline.")
        result = extract_symbol_outline(target, filename=request.query or "snippet.py")
        data = result.model_dump(mode="json")
        return VerificationExecution(
            check=self.name,
            status=VerificationStatus.NOT_CHECKED,
            data=data,
            subject_kind="source_outline",
            subject=target,
            producer="core.search.symbol_indexer.extract_symbol_outline",
            evidence_payload={"symbol_count": len(data.get("symbols") or [])},
            limitations=("Symbol extraction is analysis, not correctness verification.",),
        )


class CallGraphVerifier:
    name = "callgraph"

    async def verify(self, request: VerifierRequest, context: VerifierContext) -> VerificationExecution:
        from core.search.symbol_indexer import extract_call_graph

        target = request.code or request.draft
        if not target.strip():
            raise VerificationInputError("code or draft is required for check=callgraph.")
        result = extract_call_graph(target, filename=request.query or "snippet.py")
        data = result.model_dump(mode="json")
        return VerificationExecution(
            check=self.name,
            status=VerificationStatus.NOT_CHECKED,
            data=data,
            subject_kind="source_callgraph",
            subject=target,
            producer="core.search.symbol_indexer.extract_call_graph",
            evidence_payload={"edge_count": len(data.get("edges") or [])},
            limitations=("Call-graph extraction is analysis, not runtime verification.",),
        )


class GroundingVerifier:
    name = "grounding"

    async def verify(self, request: VerifierRequest, context: VerifierContext) -> VerificationExecution:
        from core.evidence.grounded_search import grounded_evidence, grounding_check

        if not request.draft.strip() or not request.query.strip():
            raise VerificationInputError("grounding check needs query and draft.")
        evidence = await grounded_evidence(request.query.strip())
        report = grounding_check(request.draft, evidence)
        report["evidence"] = evidence.to_dict()
        definitive_failure = bool(report.get("hallucinated_urls") or report.get("unsupported_quotes"))
        if definitive_failure:
            status = VerificationStatus.FAIL
        elif evidence.degraded:
            status = VerificationStatus.UNKNOWN
        else:
            status = status_from_bool(bool(report.get("passed")))
        limitations = list(evidence.uncertain)
        if evidence.degraded:
            limitations.append("Grounding coverage is incomplete because retrieval is degraded.")
        return VerificationExecution(
            check=self.name,
            status=status,
            data=report,
            subject_kind="grounding_draft",
            subject=f"{request.query.strip()}\0{request.draft}",
            producer="core.evidence.grounded_search.grounding_check",
            evidence_payload={
                "passed": bool(report.get("passed")),
                "hallucinated_urls": list(report.get("hallucinated_urls") or []),
                "unsupported_quotes": list(report.get("unsupported_quotes") or []),
                "degraded": evidence.degraded,
                "quote_count": len(evidence.quotes),
            },
            limitations=tuple(dict.fromkeys(limitations)),
        )


def build_core_verifier_registry(store: Any) -> VerifierRegistry:
    registry = VerifierRegistry(VerifierContext(store=store))
    for verifier in (
        ConstraintVerifier(),
        OutcomeVerifier(),
        EvidenceVerifier(),
        SyntaxVerifier(),
        TestCommandVerifier(),
        GitDiffVerifier(),
        CegisVerifier(),
        DiagnosticVerifier(),
        TypeVerifier(),
        SymbolOutlineVerifier(),
        CallGraphVerifier(),
        GroundingVerifier(),
    ):
        registry.register(verifier)
    return registry


GLOBAL_VERIFIER_REGISTRY = VerifierRegistry()
