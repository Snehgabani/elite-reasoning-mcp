import argparse
import asyncio
import json
import os
import shlex
import shutil
import subprocess
import sys
import uuid
import warnings
from typing import Any

from core.identity.user_profile import UserProfile
from core.logging_config import get_logger
from core.memory.persistent_store import EliteStore
from core.runtime import (
    PACKAGE_NAME,
    SUPPORTED_TOOL_PROFILES,
    package_version,
    resolve_tool_profile,
    runtime_identity,
)
from core.tools.error_boundary import smart_wrap

# Filter benign FastMCP / Pydantic forward reference warning in Python 3.13
warnings.filterwarnings("ignore", module="pydantic_settings")

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from fastmcp import FastMCP  # type: ignore[no-redef]

logger = get_logger(__name__)

# ── Security: Allowlisted config keys ──────────────────────
CONFIG_ALLOWLIST = frozenset(
    {
        "display_name",
        "sync.enabled",
        "sync.auto_sync_on_boot",
        "orchestration.mode",
        "orchestration.auto_scan_interval",
        "ui.theme",
        "ui.compact_mode",
    }
)


def create_mcp_server(brain_dir: str, tool_profile: str | None = None) -> FastMCP:
    """
    Creates and configures the Elite Reasoning FastMCP Server.
    Each user gets their own personalized server instance with:
      - Isolated brain (elite.db, elite_graph.db)
      - A compact v2 public surface by default
      - An explicit legacy profile for existing integrations
    """
    profile_name = resolve_tool_profile(tool_profile)
    mcp = FastMCP(
        "EliteVerify",
        instructions=(
            "Deterministic verification oracle and workflow integrity for coding agents. This server proves correctness "
            "and enforces validation gates. For every non-trivial task call elite_prepare once, retain run_id, and inspect the "
            "continuation object after EVERY Elite response. When continuation.stop_final_response is true, call "
            "continuation.required_tool with continuation.required_args before answering. Deliver the final response "
            "only at checkpoint=done. MCP cannot force another host call; the client must honor this lifecycle."
        ),
        website_url="https://github.com/Snehgabani/elite-verify-mcp",
    )
    # FastMCP currently omits a version constructor argument even though the
    # low-level MCP server supports it. Set the protocol identity explicitly so
    # clients can detect stale installations correctly.
    mcp._mcp_server.version = package_version()
    setattr(mcp, "_elite_tool_profile", profile_name)
    logger.info(
        "MCP server starting",
        extra={"action": "init", "brain_dir": brain_dir, "tool_profile": profile_name},
    )

    # ── User Profile ───────────────────────────────────────
    elite_dir = os.path.dirname(os.path.abspath(brain_dir))
    profile = UserProfile(elite_dir)
    profile.ensure_dirs()
    logger.info("User profile loaded", extra={"user": profile.config.get("user_name", "unknown")})

    # Use the profile's brain_dir if the passed-in dir matches default layout
    actual_brain_dir = brain_dir
    os.makedirs(actual_brain_dir, exist_ok=True)

    # ── Persistence ────────────────────────────────────────
    store = EliteStore(actual_brain_dir)
    # Diagnostics and the CLI use these explicit references instead of
    # reconstructing a second store/profile with subtly different state.
    setattr(mcp, "_elite_store", store)
    setattr(mcp, "_elite_profile", profile)
    logger.info("EliteStore initialized", extra={"action": "store_init"})

    # ── Seed Prevention Rules ──────────────────────────────
    _seed_prevention_rules(store)

    from core.tools import gateway

    gateway.register(mcp, store, profile)
    logger.info("Core gateway tools registered", extra={"action": "core_tools_registered"})
    return _finalize_core_server(mcp, store)


def _finalize_core_server(mcp: FastMCP, store: EliteStore) -> FastMCP:
    """Apply core middleware without constructing the legacy server surface."""
    optimization_loop = None
    try:
        from core.scheduler.optimizer import OptimizationLoop

        optimization_loop = OptimizationLoop(store)
    except ImportError as exc:
        logger.debug("OptimizationLoop not available", extra={"error": str(exc)})

    middleware_chain = None
    try:
        from core.middleware.chain import MiddlewareChain
        from core.middleware.fallback import FallbackMiddleware, RetryMiddleware
        from core.middleware.injection import AntiPatternInjectionMiddleware
        from core.middleware.prevention import PreventionRuleMiddleware
        from core.middleware.telemetry import (
            CostTrackingMiddleware,
            LatencyBudgetMiddleware,
            PeriodicScanMiddleware,
            UsageLogMiddleware,
        )

        middleware_chain = (
            MiddlewareChain()
            .use(UsageLogMiddleware(store))
            .use(LatencyBudgetMiddleware(p99_ms=2000))
            .use(PreventionRuleMiddleware(store))
            .use(AntiPatternInjectionMiddleware(store))
            .use(PeriodicScanMiddleware(store, interval=20, optimizer=optimization_loop))
            .use(CostTrackingMiddleware(store))
            .use(FallbackMiddleware())
            .use(RetryMiddleware(max_retries=2, initial_delay=0.5))
        )
    except ImportError as exc:
        logger.warning("Core middleware chain unavailable", extra={"error": str(exc)})

    session_id = f"mcp_{uuid.uuid4().hex[:8]}"
    logger.info("Core session ID assigned", extra={"session_id": session_id})
    _wrap_tools_with_error_boundary(mcp)

    if middleware_chain is not None:
        from core.integration.middleware_setup import wrap_registered_tools

        wrapped = wrap_registered_tools(mcp, middleware_chain)
        logger.info("Core middleware connected", extra={"wrapped": wrapped})
    else:
        logger.warning("Core tools are running without orchestration middleware")
    return mcp




def _wrap_tools_with_error_boundary(mcp: FastMCP):
    """
    Gap #6 Fix: Post-registration hook that wraps every registered tool's
    function with the safe_tool error boundary.

    Uses smart_wrap to auto-detect sync/async and apply the correct wrapper.
    This ensures that even if a tool module forgot to use @safe_tool,
    the boundary is applied globally.
    """
    wrapped_count = 0
    try:
        tool_manager = mcp._tool_manager
        for tool_name, tool_obj in tool_manager._tools.items():
            original_fn = tool_obj.fn
            # Don't double-wrap
            if not getattr(original_fn, "_has_error_boundary", False):
                tool_obj.fn = smart_wrap(original_fn)
                wrapped_count += 1
        logger.info("Error boundary applied", extra={"wrapped": wrapped_count})
    except Exception as e:
        logger.warning("Error boundary wrapping failed", extra={"error": str(e)})




def _seed_prevention_rules(store: EliteStore):
    """Seed initial prevention rules from known failure patterns.
    Uses idempotent registration — existing rules are NOT overwritten.

    Blueprint #5 Fix: Uses CANONICAL EVENT VOCABULARY instead of ad-hoc trigger names.
    Old vocabulary (before_design, on_prompt, etc.) is migrated at runtime by EventBus.
    """
    rules = [
        # ── P0: Must never miss ──
        (
            "no_silent_stops",
            "tool.after:*",
            "Check if multi-step task is in progress and system is about to stop",
            "Continue execution — never stop a multi-step task without a blocking reason",
            "P0",
        ),
        (
            "architecture_checklist",
            "phase.before:design",
            "Run internal checklist: error recovery, observability, permissions, UX, export, updates, testing, monitoring",
            "Pre-populate design with all checklist items before presenting to user",
            "P0",
        ),
        (
            "verify_before_commit",
            "phase.before:code_change",
            "Run a quick smoke test on any API usage before committing",
            "Execute verification command for new API patterns",
            "P0",
        ),
        # ── P1: Should fire but non-blocking ──
        (
            "escalation_detection",
            "prompt.received",
            "Detect if user is escalating from specific to general in <= 3 prompts",
            "Switch to architecture mode instead of task-execution mode",
            "P1",
        ),
        (
            "track_implicit_requirements",
            "prompt.received",
            "When user mentions a constraint (non-coder, production, etc), record it",
            "Apply recorded constraints to all subsequent designs",
            "P1",
        ),
        (
            "self_audit_findings",
            "phase.after:audit",
            "Check if all findings from previous audits have been resolved",
            "Flag unresolved findings before starting new work",
            "P1",
        ),
        (
            "gap_analysis_before_present",
            "phase.before:design",
            "Ask internally: what did I NOT mention that a senior architect would?",
            "Add missing items before presenting to user",
            "P1",
        ),
        (
            "detect_repetition",
            "prompt.received",
            "Count 'go'/'continue' prompts — if > 2 in sequence, user is frustrated",
            "Set auto_continue mode and acknowledge the pattern",
            "P1",
        ),
        # ── P2: Nice to have ──
        (
            "crash_recovery_check",
            "session.start",
            "Check for incomplete operations from previous session",
            "Resume from last checkpoint",
            "P2",
        ),
        (
            "test_coverage_gate",
            "phase.after:code_change",
            "Verify new code has corresponding tests",
            "Generate test stubs for untested code",
            "P2",
        ),
    ]
    seeded = 0
    for name, trigger, check, action, severity in rules:
        try:
            store.register_prevention_rule(name, trigger, check, action, severity)
            seeded += 1
        except Exception as e:
            logger.debug(f"Prevention rule seeding skipped for {name}: {e}")
    logger.info("Prevention rules seeded", extra={"new": seeded, "total": len(rules)})


def _execute_prevention_rules(store: EliteStore, trigger_event: str, context: dict) -> list[str]:
    """Execute all enabled prevention rules matching the trigger event.
    Returns a list of warning strings for rules that matched."""
    warnings = []
    try:
        rules = store.get_active_prevention_rules(trigger_event)
        for rule in rules:
            try:
                # Check if the rule's check matches the context
                check = rule.get("check", "").lower()
                action = rule.get("action", "")
                tool_name = context.get("tool_name", "")
                args_text = context.get("args_text", "")
                combined = f"{tool_name} {args_text}".lower()

                # Keyword-based matching — check if the rule's query concepts appear in context
                check_words = [w for w in check.split() if len(w) > 3]  # Skip short words
                if check_words:
                    match_count = sum(1 for w in check_words if w in combined)
                    match_ratio = match_count / len(check_words)

                    if match_ratio >= 0.3:  # 30% keyword overlap = match
                        store.increment_rule_trigger(rule["id"])
                        warnings.append(
                            f"🛡️ Rule `{rule['name']}` [{rule['severity']}] fired:\n"
                            f"   Check: {check}\n"
                            f"   Action: {action}"
                        )
            except Exception as e:
                logger.debug(f"Individual rule evaluation failed: {e}")
    except Exception as e:
        logger.debug(f"Rule system retrieval failed: {e}")
    return warnings




def _default_brain_dir() -> str:
    return os.environ.get("ELITE_BRAIN_DIR", os.path.expanduser("~/.elite-reasoning/brain"))


def _upgrade_command() -> list[str]:
    """Choose the package manager that matches a standalone installation."""
    uv = shutil.which("uv")
    if uv:
        return [uv, "tool", "upgrade", PACKAGE_NAME]
    return [sys.executable, "-m", "pip", "install", "--upgrade", PACKAGE_NAME]


async def _run_demo(server) -> dict[str, Any]:
    """Exercise the installed five-tool core without network access."""
    prompt = "Reply in JSON. At most 20 words. Do not mention tools."
    tools = server._tool_manager._tools
    prepared = await tools["elite_prepare"].fn(user_prompt=prompt, persist=False)
    failing = await tools["elite_verify"].fn(
        check="constraints",
        query=prompt,
        draft="I will use tools and provide a long unstructured explanation instead of JSON.",
    )
    passing_draft = '{"ok":true,"reason":"requirements satisfied"}'
    passing = await tools["elite_verify"].fn(check="constraints", query=prompt, draft=passing_draft)
    return {
        "status": "ok"
        if failing.verification_status.value == "FAIL" and passing.verification_status.value == "PASS"
        else "failed",
        "offline": True,
        "persisted": prepared.persisted,
        "tool_count": len(tools),
        "contract_schema_version": prepared.task_contract.get("schema_version"),
        "constraints": prepared.task_contract.get("constraints", []),
        "failing_draft": {
            "verification_status": failing.verification_status.value,
            "unmet": failing.data.get("unmet", []),
            "subject_digest": failing.subject_digest,
            "evidence_id": failing.evidence[0].id,
        },
        "passing_draft": {
            "verification_status": passing.verification_status.value,
            "unmet": passing.data.get("unmet", []),
            "subject_digest": passing.subject_digest,
            "evidence_id": passing.evidence[0].id,
        },
        "privacy": {
            "raw_prompt_persisted": False,
            "network_requests": 0,
        },
    }


def _demo_markdown(report: dict[str, Any]) -> str:
    failing = report["failing_draft"]
    passing = report["passing_draft"]
    return "\n".join(
        [
            "# Elite Reasoning MCP Offline Demo",
            "",
            f"- Core tools discovered: {report['tool_count']}",
            f"- Contract schema: {report['contract_schema_version']}",
            f"- Intentionally invalid draft: {failing['verification_status']}",
            f"- Corrected draft: {passing['verification_status']}",
            f"- Raw prompt persisted: {str(report['privacy']['raw_prompt_persisted']).lower()}",
            f"- Network requests: {report['privacy']['network_requests']}",
            "",
            "The demo passes only when the bad draft fails and the corrected draft passes.",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    """Run the MCP server or an explicit local maintenance command."""
    parser = argparse.ArgumentParser(prog=PACKAGE_NAME)
    parser.add_argument(
        "--tool-profile",
        choices=sorted(SUPPORTED_TOOL_PROFILES),
        default=None,
        help="Public tool surface; defaults to the compact core profile.",
    )
    parser.add_argument("--brain-dir", default=_default_brain_dir(), help="Path to local Elite state.")
    parser.add_argument("--version", action="store_true", help="Print the installed package version and exit.")
    subcommands = parser.add_subparsers(dest="command")
    doctor_parser = subcommands.add_parser("doctor", help="Run local release diagnostics.")
    doctor_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    doctor_parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero unless the report is release-ready.",
    )
    demo_parser = subcommands.add_parser("demo", help="Run an offline end-to-end core verification demo.")
    demo_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    init_parser = subcommands.add_parser("init", help="Preview or install one IDE MCP configuration.")
    init_parser.add_argument("--ide", required=True, help="Cursor, Claude Desktop, Windsurf, Zed, or Antigravity.")
    init_parser.add_argument("--dry-run", action="store_true", help="Print the merged config without writing it.")
    init_parser.add_argument("--yes", action="store_true", help="Confirm the atomic configuration write.")
    init_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    export_parser = subcommands.add_parser("export-evidence", help="Export redacted evidence for one workflow run.")
    export_parser.add_argument("run_id", help="Persisted workflow run ID.")
    export_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    upgrade_parser = subcommands.add_parser("upgrade", help="Upgrade the standalone package explicitly.")
    upgrade_parser.add_argument("--yes", action="store_true", help="Confirm the package-manager upgrade command.")
    upgrade_parser.add_argument("--dry-run", action="store_true", help="Print the upgrade command without running it.")

    args = parser.parse_args(argv)
    if args.version:
        print(package_version())
        return 0

    if args.command == "upgrade":
        command = _upgrade_command()
        if args.dry_run:
            print(shlex.join(command))
            return 0
        if not args.yes:
            print("Refusing to upgrade without --yes. Use --dry-run to inspect the command.", file=sys.stderr)
            return 2
        return subprocess.run(command, check=False).returncode

    if args.command == "init":
        from core.orchestration.ide_installer import IDEConfigError, MultiIDEInstaller

        installer = MultiIDEInstaller(binary_path=runtime_identity()["entrypoint"])
        try:
            target = installer.target_for(args.ide)
            if args.dry_run:
                result = installer.preview_target(target)
            elif args.yes:
                result = installer.install_to_target(target)
            else:
                print("Refusing to modify IDE configuration without --yes. Use --dry-run to preview.", file=sys.stderr)
                return 2
        except IDEConfigError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(
            json.dumps(result, indent=2, sort_keys=True)
            if args.json or args.dry_run
            else f"Installed {result['ide']}: {result['path']}"
        )
        return 0

    server = create_mcp_server(args.brain_dir, tool_profile=args.tool_profile)
    if args.command == "export-evidence":
        store = getattr(server, "_elite_store")
        run = store.get_workflow_run(args.run_id)
        if run is None:
            print("Workflow run was not found.", file=sys.stderr)
            return 2
        evidence = store.list_workflow_evidence(args.run_id, limit=200)
        report = {
            "schema_version": "1.0",
            "run_id": args.run_id,
            "workflow_status": run.get("status"),
            "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at"),
            "evidence_count": len(evidence),
            "evidence": evidence,
        }
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(
                f"# Workflow Evidence: {args.run_id}\n\nStatus: `{report['workflow_status']}`\n\nEvidence records: {len(evidence)}"
            )
            for item in evidence:
                print(f"- `{item['verification_status']}` {item['check_kind']} — `{item['id']}`")
        return 0
    if args.command == "demo":
        report = asyncio.run(_run_demo(server))
        print(json.dumps(report, indent=2, sort_keys=True) if args.json else _demo_markdown(report))
        return 0 if report["status"] == "ok" else 1
    if args.command == "doctor":
        from core.tools.doctor import build_doctor_report, doctor_markdown

        report = build_doctor_report(
            getattr(server, "_elite_store"),
            profile=getattr(server, "_elite_profile"),
            mcp=server,
        )
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(doctor_markdown(report))
        return 1 if args.strict and report["status"] != "release_ready" else 0

    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
