import os
import uuid

from mcp.server.fastmcp import FastMCP

from core.identity.user_profile import UserProfile
from core.logging_config import get_logger
from core.memory.persistent_store import EliteStore
from core.tools.error_boundary import smart_wrap

logger = get_logger(__name__)

# ── Security: Allowlisted config keys ──────────────────────
CONFIG_ALLOWLIST = frozenset({
    "display_name",
    "sync.enabled",
    "sync.auto_sync_on_boot",
    "orchestration.mode",
    "orchestration.auto_scan_interval",
    "ui.theme",
    "ui.compact_mode",
})

# ── Security: Allowed sync hub domains ─────────────────────
ALLOWED_HUB_DOMAINS = frozenset({
    "localhost",
    "127.0.0.1",
    "elite-sync.local",
})


def create_mcp_server(brain_dir: str) -> FastMCP:
    """
    Creates and configures the Elite Reasoning FastMCP Server.
    Each user gets their own personalized server instance with:
      - Isolated brain (elite.db, elite_graph.db)
      - Personalized orchestration (scans THEIR installed MCPs/Skills)
      - User identity for sync attribution
    """
    mcp = FastMCP("EliteReasoning")
    logger.info("MCP server starting", extra={"action": "init", "brain_dir": brain_dir})

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
    logger.info("EliteStore initialized", extra={"action": "store_init"})

    # ── Seed Prevention Rules ──────────────────────────────
    _seed_prevention_rules(store)

    # ── Register Tool Modules (legacy individual tools) ────
    from core.integration import memory_bridge
    from core.tools import adaptive, analysis, auditing, graph_tools, orchestration, planning, reasoning_amplifier

    planning.register(mcp, store)
    auditing.register(mcp, store)
    analysis.register(mcp, store)
    graph_tools.register(mcp, store)
    orchestration.register(mcp, store)
    adaptive.register(mcp, store)
    reasoning_amplifier.register(mcp, store)
    memory_bridge.register(mcp, store)
    logger.info("Tool modules registered", extra={"action": "tools_registered"})

    # ── Register Verb Tools (Blueprint #1: 66→8 surface) ──
    from core.tools.verb_tools import register_verb_tools
    register_verb_tools(mcp, store)

    # ── Build Middleware Chain (Blueprint #3: replaces monkey-patch) ──
    # Opus R2: Correct order matters critically:
    #   1. UsageLog    — FIRST: logs even blocked calls (auditable)
    #   2. Latency     — brackets entire call incl. middleware overhead
    #   3. Prevention  — pre-execution check (can short-circuit)
    #   4. Injection   — context augmentation (anti-pattern warnings)
    #   5. PeriodicScan — lightweight post-hook (autonomous gap detection)
    #   6. Fallback    — suggests alternatives on failure
    #   7. Retry       — INNERMOST: avoids duplicate injections/prevention evals
    # ── Optimization Loop (5-trigger autonomy controller) ──
    # Must be initialized BEFORE middleware chain so it can be wired in.
    _optimization_loop = None
    try:
        from core.scheduler.optimizer import OptimizationLoop
        _optimization_loop = OptimizationLoop(store)
        logger.info("OptimizationLoop initialized (5 triggers, hook-based)")
    except ImportError as e:
        logger.debug(f"OptimizationLoop not available: {e}")

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

        _middleware_chain = (
            MiddlewareChain()
            .use(UsageLogMiddleware(store))                                # 1. Log EVERYTHING (even blocked)
            .use(LatencyBudgetMiddleware(p99_ms=2000))                     # 2. Bracket entire call
            .use(PreventionRuleMiddleware(store))                          # 3. Pre-execution check
            .use(AntiPatternInjectionMiddleware(store))                    # 4. Context augmentation
            .use(PeriodicScanMiddleware(store, interval=20,
                                       optimizer=_optimization_loop))      # 5. Post-hook scan + optimizer tick
            .use(CostTrackingMiddleware(store))                            # 6. Auto-log embedding costs
            .use(FallbackMiddleware())                                     # 7. Suggest alternatives on fail
            .use(RetryMiddleware(max_retries=2, initial_delay=0.5))        # 8. Retry INNERMOST
        )
        logger.info("Middleware chain built (R2 order)", extra={"middlewares": 8,
                    "optimizer_wired": _optimization_loop is not None})
    except ImportError as e:
        _middleware_chain = None
        logger.warning("Middleware chain not available, falling back to interceptor", extra={"error": str(e)})


    # ── User Identity Tools ────────────────────────────────

    @mcp.tool()
    def get_user_profile() -> str:
        """
        Returns the current user's profile, including their identity,
        IDE type, installed MCP/Skill counts, sync status, and preferences.
        Use this to understand WHO you are serving and what tools they have.
        """
        return profile.get_profile_summary()

    @mcp.tool()
    def update_user_config(key: str, value: str) -> str:
        """
        Update a user's personalization setting.
        Args:
            key: Dot-notation path (e.g., 'sync.enabled', 'orchestration.mode', 'display_name')
            value: New value (strings are auto-converted to bool/int when appropriate)
        """
        # SECURITY: Only allow pre-approved config keys
        if key not in CONFIG_ALLOWLIST:
            return f"❌ Config key `{key}` is not in the allowlist. Allowed: {', '.join(sorted(CONFIG_ALLOWLIST))}"

        parts = key.split(".")
        cfg = profile.config

        # Navigate to parent
        target = cfg
        for p in parts[:-1]:
            if p not in target or not isinstance(target[p], dict):
                return f"❌ Invalid config path: {key}"
            target = target[p]

        final_key = parts[-1]
        if final_key not in target:
            return f"❌ Unknown config key: {key}"

        # Auto-convert types
        old_type = type(target[final_key])
        if old_type is bool:
            parsed = value.lower() in ("true", "1", "yes")
        elif old_type is int:
            try:
                parsed = int(value)
            except ValueError:
                return f"❌ Expected integer for `{key}`, got: {value}"
        elif old_type is list:
            parsed = [v.strip() for v in value.split(",")]
        else:
            parsed = value

        target[final_key] = parsed
        profile.save()
        return f"✅ Updated `{key}`: `{target[final_key]}`"

    @mcp.tool()
    def list_team_users(hub_url: str = "") -> str:
        """
        List all users registered with the team sync hub.
        Shows each user's IDE type, MCP count, and skill count.
        Args:
            hub_url: Override sync hub URL (default: from user config)
        """
        from urllib.parse import urlparse

        import httpx

        url = hub_url or profile.sync_hub_url
        url = url.rstrip("/")

        # SECURITY: Validate hub URL against allowed domains (SSRF prevention)
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        if hostname not in ALLOWED_HUB_DOMAINS:
            return f"❌ Hub URL `{hostname}` is not in the allowed domains: {', '.join(sorted(ALLOWED_HUB_DOMAINS))}"

        headers = {}
        if profile.sync_api_key:
            headers["X-Elite-Sync-Key"] = profile.sync_api_key

        try:
            resp = httpx.get(f"{url}/api/users", headers=headers, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()

            total = data.get("total_users", 0)
            users = data.get("users", {})

            if total == 0:
                return "No users registered with the sync hub yet."

            out = f"# Team Users ({total} total)\n\n"
            out += "| User | IDE | MCPs | Skills | Registered |\n"
            out += "|---|---|---|---|---|\n"
            for uid, info in users.items():
                out += (
                    f"| {info.get('display_name', uid)} | "
                    f"{info.get('ide_type', '?')} | "
                    f"{info.get('mcp_count', '?')} | "
                    f"{info.get('skill_count', '?')} | "
                    f"{info.get('registered_at', '?')} |\n"
                )
            return out

        except httpx.ConnectError:
            return f"❌ Cannot reach sync hub at `{url}`. Is it running?"
        except Exception as e:
            return f"❌ Error listing team users: {e}"

    @mcp.tool()
    def share_skill(skill_name: str, description: str = "") -> str:
        """
        Publish one of your locally installed skills to the team hub so other
        users can discover and install it.
        Args:
            skill_name: Name of the skill to share
            description: Optional description override
        """
        import httpx

        from core.tools.orchestration import scan_available_skills

        skills = scan_available_skills()
        if skill_name not in skills:
            return f"❌ Skill `{skill_name}` not found in your installation. Available: {', '.join(skills[:20])}..."

        # Add to local shared list
        shared = profile.config.get("shared_skills", [])
        if skill_name not in shared:
            shared.append(skill_name)
            profile.config["shared_skills"] = shared
            profile.save()

        # Push to hub if sync is enabled
        if profile.sync_enabled:
            url = profile.sync_hub_url.rstrip("/")
            headers = {}
            if profile.sync_api_key:
                headers["X-Elite-Sync-Key"] = profile.sync_api_key
            try:
                httpx.post(
                    f"{url}/api/skills/share",
                    headers=headers,
                    json={
                        "user_id": profile.user_id,
                        "skill_name": skill_name,
                        "description": description,
                    },
                    timeout=10.0,
                )
            except Exception as e:
                logger.debug(f'Skill share HTTP request failed: {e}')

        return f"✅ Skill `{skill_name}` shared. Other team members will see it after their next sync."

    # ==================================================================
    # RESOURCES — Read-Only Context
    # ==================================================================

    @mcp.resource("elite://profile")
    def get_profile_resource() -> str:
        """Current user's identity, preferences, and environment."""
        return profile.get_profile_summary()

    @mcp.resource("elite://anti_patterns")
    def get_anti_patterns_resource() -> str:
        """Full anti-pattern registry — all known mistakes and fixes."""
        patterns = store.get_all_anti_patterns()
        if not patterns:
            return "Anti-pattern registry is empty."
        out = "# 🛡️ Anti-Pattern Registry\n\n"
        for p in patterns:
            out += f"## [{p['severity'].upper()}] {p['mistake']}\n- Root Cause: {p['root_cause']}\n- Fix: {p['fix']}\n\n"
        return out

    @mcp.resource("elite://decisions")
    def get_decisions_resource() -> str:
        """All architectural decisions and their rationale."""
        decisions = store.get_all_decisions()
        if not decisions:
            return "No decisions recorded yet."
        out = "# 📝 Decision Journal\n\n"
        for d in decisions:
            out += f"## {d['decision']}\n- Rationale: {d['rationale']}\n- _Decided: {d['created_at']}_\n\n"
        return out

    @mcp.resource("elite://quality")
    def get_quality_resource() -> str:
        """Quality score dashboard and trend data."""
        t = store.get_quality_trend()
        if t["trend"] == "no_data":
            return "No quality data recorded."
        out = f"# 📊 Quality Dashboard\n\nAvg: {t['average']}/100 | Trend: {t['trend']} | Points: {t['count']}\n\n"
        out += "| Score | Dimension | Date | Notes |\n|---|---|---|---|\n"
        for s in t["scores"]:
            out += f"| {s['score']} | {s['dimension']} | {s['date']} | {s['notes'] or '-'} |\n"
        return out

    # ── Gap #5 Fix: Health Check Resource ──────────────────
    @mcp.resource("elite://health")
    def get_health_resource() -> str:
        """System health check — reports dependency status and degradation."""
        import importlib
        checks = []

        # Check sqlite_vec
        try:
            import sqlite_vec  # noqa: F401
            checks.append("| sqlite_vec | ✅ Installed | Full vector search available |")
        except ImportError:
            checks.append("| sqlite_vec | ❌ Missing | Falling back to FTS text search |")

        # Check sentence-transformers
        try:
            importlib.import_module("sentence_transformers")
            checks.append("| sentence-transformers | ✅ Installed | Semantic embeddings active |")
        except ImportError:
            checks.append("| sentence-transformers | ❌ Missing | Semantic search degraded |")

        # Check embedding model
        try:
            from core.memory.embedding_service import EmbeddingService
            if isinstance(getattr(store, '_embedding_service', None), EmbeddingService):
                checks.append("| Embedding Model | ✅ Loaded | Ready for encoding |")
            elif hasattr(store, 'embedding_model') and store.embedding_model:
                checks.append("| Embedding Model | ✅ Loaded | Ready for encoding |")
            else:
                checks.append("| Embedding Model | ⚠️ Not loaded | Will load on first use |")
        except ImportError:
            # EmbeddingService not available, fall back to hasattr check
            try:
                if hasattr(store, 'embedding_model') and store.embedding_model:
                    checks.append("| Embedding Model | ✅ Loaded | Ready for encoding |")
                else:
                    checks.append("| Embedding Model | ⚠️ Not loaded | Will load on first use |")
            except Exception as e:
                logger.debug(f'Embedding model check failed: {e}')
                checks.append("| Embedding Model | ❌ Error | Embedding generation unavailable |")
        except Exception as e:
            logger.debug(f'Embedding availability check failed: {e}')
            checks.append("| Embedding Model | ❌ Error | Embedding generation unavailable |")

        # Check databases
        try:
            count = store.count_anti_patterns()
            checks.append(f"| elite.db | ✅ Connected | {count} anti-patterns stored |")
        except Exception as e:
            checks.append(f"| elite.db | ❌ Error | {e} |")

        status = "✅ Healthy" if all("✅" in c for c in checks[:2]) else "⚠️ Degraded"
        out = f"# Elite MCP Health\n\n**Status:** {status}\n\n"
        out += "| Component | Status | Detail |\n|---|---|---|\n"
        for c in checks:
            out += c + "\n"
        out += f"\n**User:** {profile.user_id} | **IDE:** {profile.ide_type}\n"
        return out

    @mcp.resource("elite://goals")
    def get_goals_resource() -> str:
        """Active goals and their progress (OKR-style tracking)."""
        goals = store.get_active_goals()
        if not goals:
            return "No active goals. Use `set_goal` to create one."
        out = "# 🎯 Active Goals\n\n"
        for g in goals:
            kr = g.get("key_results", [])
            prog = g.get("progress", {})
            overall = g.get("overall_pct", 0)
            bar_filled = int(overall / 5)
            bar = "█" * bar_filled + "░" * (20 - bar_filled)
            out += f"### #{g['id']}: {g['objective']}\n"
            out += f"Progress: [{bar}] {overall:.0f}%\n\n"
            for k in kr:
                p = prog.get(k, 0)
                out += f"  - {k}: **{p}%**\n"
            out += f"\n_Set: {g['created_at']} | Updated: {g['updated_at']}_\n\n"
        return out

    @mcp.resource("elite://benchmarks")
    def get_benchmarks_resource() -> str:
        """Benchmark baselines and tracking data."""
        conn = store._connect()
        c = conn.cursor()
        c.execute("SELECT metric, value, unit, context, created_at FROM benchmarks ORDER BY created_at DESC LIMIT 50")
        rows = c.fetchall()
        store._close(conn)
        if not rows:
            return "No benchmarks recorded. Use `benchmark_track` to establish baselines."
        out = "# 📈 Benchmarks\n\n"
        out += "| Metric | Value | Unit | Context | Date |\n|---|---|---|---|---|\n"
        for r in rows:
            out += f"| {r[0]} | {r[1]} | {r[2] or '-'} | {r[3] or '-'} | {r[4]} |\n"
        return out

    # ── Auto-Sync on Boot ──────────────────────────────────
    if profile.sync_enabled and profile.config.get("sync", {}).get("auto_sync_on_boot", False):
        import threading

        def _boot_sync():
            try:
                import httpx
                url = profile.sync_hub_url.rstrip("/")
                headers = {}
                if profile.sync_api_key:
                    headers["X-Elite-Sync-Key"] = profile.sync_api_key

                from core.tools.orchestration import scan_available_mcps, scan_available_skills
                httpx.post(
                    f"{url}/api/users/register",
                    headers=headers,
                    json={
                        "user_id": profile.user_id,
                        "display_name": profile.display_name,
                        "ide_type": profile.ide_type,
                        "mcp_count": len(scan_available_mcps()),
                        "skill_count": len(scan_available_skills()),
                    },
                    timeout=5.0,
                )
            except Exception as e:
                logger.debug(f'Boot sync HTTP request failed: {e}')

        threading.Thread(target=_boot_sync, daemon=True).start()

    # ── Unique Session ID per MCP restart ──────────────────
    _session_id = f"mcp_{uuid.uuid4().hex[:8]}"
    logger.info("Session ID assigned", extra={"session_id": _session_id})

    # ── Gap #6+#11 Fix: Wrap ALL tools (moved to end so identity tools are included)
    _wrap_tools_with_error_boundary(mcp)

    # ── Execution Path Selection ──────────────────────────────
    # Default: Middleware chain (R2 architecture)
    # Legacy: Monkey-patch interceptor (opt-in via env var for debugging)
    if os.environ.get('ELITE_ENABLE_LEGACY_INTERCEPTOR', '').strip() == '1':
        logger.warning("Legacy interceptor enabled via ELITE_ENABLE_LEGACY_INTERCEPTOR=1")
        _install_orchestration_interceptor(mcp, store, _session_id)
    elif _middleware_chain is not None:
        from core.integration.middleware_setup import wrap_registered_tools
        wrapped = wrap_registered_tools(mcp, _middleware_chain)
        logger.info("Middleware chain connected to tools",
                    extra={"wrapped": wrapped, "path": "middleware_chain"})
    else:
        logger.warning("No middleware chain available and legacy interceptor disabled — "
                      "tools will run without orchestration hooks")

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
            if not getattr(original_fn, '_has_error_boundary', False):
                tool_obj.fn = smart_wrap(original_fn)
                wrapped_count += 1
        logger.info("Error boundary applied", extra={"wrapped": wrapped_count})
    except Exception as e:
        logger.warning("Error boundary wrapping failed", extra={"error": str(e)})


def _classify_intent(prompt: str) -> str:
    """Weighted multi-signal intent classifier.
    Returns the highest-scoring category based on keyword matches."""
    p = prompt.lower()
    scores = {
        'debug': 0, 'audit': 0, 'build': 0, 'improve': 0,
        'investigate': 0, 'continuation': 0, 'deploy': 0, 'test': 0,
        'create': 0, 'design': 0, 'decide': 0, 'evaluate': 0, 'fix': 0,
    }
    # Weight 2 = strong signal, 1 = weak signal
    signals = [
        ('debug', 2, ['debug', 'error', 'broken', 'crash', 'bug', 'traceback', 'exception', 'stack trace', 'not working']),
        ('fix', 2, ['fix', 'patch', 'hotfix', 'resolve', 'repair']),
        ('audit', 2, ['audit', 'review', 'check', 'scan', 'diagnose', 'health', 'inspect', 'verify']),
        ('build', 2, ['build', 'implement', 'add feature', 'new feature', 'scaffold', 'generate', 'write code']),
        ('create', 2, ['create', 'new project', 'bootstrap', 'setup', 'init', 'from scratch']),
        ('design', 2, ['design', 'architect', 'architecture', 'schema', 'data model', 'api design', 'system design']),
        ('decide', 2, ['decide', 'choose', 'pick', 'which one', 'should i', 'trade-off', 'tradeoff', 'vs ']),
        ('evaluate', 2, ['evaluate', 'compare', 'assess', 'benchmark', 'measure', 'analyze option', 'pros and cons']),
        ('improve', 2, ['improve', 'upgrade', 'optimize', 'refactor', 'better', 'enhance', 'polish', 'clean up']),
        ('investigate', 1, ['explain', 'how does', 'why does', 'what is', 'understand', 'show me', 'where is']),
        ('continuation', 1, ['go', 'continue', 'proceed', 'next', 'keep going', 'do it', 'execute', 'run it']),
        ('deploy', 2, ['deploy', 'push', 'release', 'publish', 'ship', 'production', 'staging']),
        ('test', 2, ['test', 'spec', 'unittest', 'e2e test', 'integration test', 'coverage', 'experiment']),
    ]
    for category, weight, keywords in signals:
        for kw in keywords:
            if kw in p:
                scores[category] += weight
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'general'


def _classify_reasoning(prompt: str) -> str:
    """Weighted reasoning-type classifier.
    Detects meta-patterns: loop kicks, depth escalation, gap injection, frustration."""
    p = prompt.lower().strip()
    # Exact-match loop kicks first (highest priority)
    if p in ('go', 'continue', 'proceed', 'next', 'keep going', 'yes', 'do it', 'ok', 'approved'):
        return 'loop_kick'
    # Depth escalation — user wants more depth
    depth_kws = ['think deeper', 'in depth', 'microscopically', 'more detail', 'not enough',
                 'go deeper', 'drill down', 'end to end', 'comprehensive', 'thorough']
    if any(kw in p for kw in depth_kws):
        return 'depth_escalation'
    # Gap injection — user adding something system missed
    gap_kws = ['also need', 'what about', 'we must', 'dont forget', 'missing',
               'we also', 'you forgot', 'didnt mention', 'overlooked', 'and also']
    if any(kw in p for kw in gap_kws):
        return 'gap_injection'
    # Frustration/repetition — user repeating themselves
    frust_kws = ['still', 'again', 'why not', 'already told', 'i said',
                 'i already', 'still not', 'same problem', 'didnt work']
    if any(kw in p for kw in frust_kws):
        return 'repetition_frustration'
    # Meta-instruction — user teaching the system
    meta_kws = ['always', 'every step', 'make sure', 'at every', 'must',
                'never', 'from now on', 'remember to', 'rule:', 'important:']
    if any(kw in p for kw in meta_kws):
        return 'meta_instruction'
    # Correction — user fixing system's output
    corr_kws = ['no,', 'not that', 'wrong', 'incorrect', 'thats not', 'i meant']
    if any(kw in p for kw in corr_kws):
        return 'correction'
    return 'substantive'


def _classify_complexity(intent: str, prompt: str) -> int:
    """Classify task complexity on a 1-5 scale.
    Combines intent category, prompt length, and keyword signals."""
    t = prompt.lower()
    score = 1

    # Length-based: longer descriptions = more complex
    if len(t) > 500:
        score += 2
    elif len(t) > 200:
        score += 1

    # Intent-based escalation
    if intent in ('deploy', 'audit'):
        score += 2
    elif intent in ('build', 'improve', 'debug'):
        score += 1

    # Critical keywords → bump to 4-5
    critical_kws = [
        'production', 'security', 'authentication', 'migration',
        'database schema', 'breaking change', 'backwards compat',
        'scale', 'concurrent', 'distributed', 'microservice',
    ]
    for kw in critical_kws:
        if kw in t:
            score += 2
            break

    # Moderate keywords → bump by 1
    moderate_kws = [
        'refactor', 'redesign', 'architecture', 'integrate',
        'api design', 'data model', 'performance', 'optimize',
        'end to end', 'full stack', 'comprehensive',
    ]
    for kw in moderate_kws:
        if kw in t:
            score += 1
            break

    # Trivial keywords → dampening
    trivial_kws = [
        'typo', 'rename', 'comment', 'format', 'lint',
        'simple', 'quick', 'minor', 'small fix',
    ]
    for kw in trivial_kws:
        if kw in t:
            score = max(1, score - 2)
            break

    return min(5, max(1, score))


def _seed_prevention_rules(store: EliteStore):
    """Seed initial prevention rules from known failure patterns.
    Uses idempotent registration — existing rules are NOT overwritten.
    
    Blueprint #5 Fix: Uses CANONICAL EVENT VOCABULARY instead of ad-hoc trigger names.
    Old vocabulary (before_design, on_prompt, etc.) is migrated at runtime by EventBus.
    """
    rules = [
        # ── P0: Must never miss ──
        ("no_silent_stops", "tool.after:*",
         "Check if multi-step task is in progress and system is about to stop",
         "Continue execution — never stop a multi-step task without a blocking reason", "P0"),
        ("architecture_checklist", "phase.before:design",
         "Run internal checklist: error recovery, observability, permissions, UX, export, updates, testing, monitoring",
         "Pre-populate design with all checklist items before presenting to user", "P0"),
        ("verify_before_commit", "phase.before:code_change",
         "Run a quick smoke test on any API usage before committing",
         "Execute verification command for new API patterns", "P0"),
        # ── P1: Should fire but non-blocking ──
        ("escalation_detection", "prompt.received",
         "Detect if user is escalating from specific to general in <= 3 prompts",
         "Switch to architecture mode instead of task-execution mode", "P1"),
        ("track_implicit_requirements", "prompt.received",
         "When user mentions a constraint (non-coder, production, etc), record it",
         "Apply recorded constraints to all subsequent designs", "P1"),
        ("self_audit_findings", "phase.after:audit",
         "Check if all findings from previous audits have been resolved",
         "Flag unresolved findings before starting new work", "P1"),
        ("gap_analysis_before_present", "phase.before:design",
         "Ask internally: what did I NOT mention that a senior architect would?",
         "Add missing items before presenting to user", "P1"),
        ("detect_repetition", "prompt.received",
         "Count 'go'/'continue' prompts — if > 2 in sequence, user is frustrated",
         "Set auto_continue mode and acknowledge the pattern", "P1"),
        # ── P2: Nice to have ──
        ("crash_recovery_check", "session.start",
         "Check for incomplete operations from previous session",
         "Resume from last checkpoint", "P2"),
        ("test_coverage_gate", "phase.after:code_change",
         "Verify new code has corresponding tests",
         "Generate test stubs for untested code", "P2"),
    ]
    seeded = 0
    for name, trigger, check, action, severity in rules:
        try:
            store.register_prevention_rule(name, trigger, check, action, severity)
            seeded += 1
        except Exception as e:
            logger.debug(f'Prevention rule seeding skipped for {name}: {e}')
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
                check = rule.get('check', '').lower()
                action = rule.get('action', '')
                tool_name = context.get('tool_name', '')
                args_text = context.get('args_text', '')
                combined = f"{tool_name} {args_text}".lower()

                # Keyword-based matching — check if the rule's query concepts appear in context
                check_words = [w for w in check.split() if len(w) > 3]  # Skip short words
                if check_words:
                    match_count = sum(1 for w in check_words if w in combined)
                    match_ratio = match_count / len(check_words)

                    if match_ratio >= 0.3:  # 30% keyword overlap = match
                        store.increment_rule_trigger(rule['id'])
                        warnings.append(
                            f"🛡️ Rule `{rule['name']}` [{rule['severity']}] fired:\n"
                            f"   Check: {check}\n"
                            f"   Action: {action}"
                        )
            except Exception as e:
                logger.debug(f'Individual rule evaluation failed: {e}')
    except Exception as e:
        logger.debug(f'Rule system retrieval failed: {e}')
    return warnings


def _install_orchestration_interceptor(mcp: FastMCP, store: EliteStore, session_id: str):
    """
    Gap #2 FIX: Transport-level orchestration pre-hook.
    
    Monkey-patches FastMCP.call_tool so that EVERY tool invocation:
    1. Executes prevention rules matching the trigger event
    2. Checks for relevant anti-patterns (past mistakes)
    3. Classifies intent on orchestration calls
    4. Runs the original tool (timed)
    5. Logs tool usage to the adaptive learning system
    6. Runs periodic autonomous scans every 20 calls
    7. Prepends all warnings/context to the tool result
    
    This ensures no tool call bypasses the orchestration system.
    """
    import time as _time
    from typing import Any, Sequence

    from mcp.types import TextContent

    # Tools exempt from the anti-pattern pre-hook (meta tools + identity tools)
    EXEMPT_TOOLS = frozenset({
        'orchestrate_request_tool',
        'get_user_profile',
        'update_user_config',
        'list_team_users',
        'share_skill',
    })

    # Mutable counter for periodic autonomous scan
    _tool_call_counter = [0]

    # Save original call_tool
    _original_call_tool = mcp.call_tool

    async def _intercepted_call_tool(name: str, arguments: dict[str, Any]) -> Sequence:
        """
        Interceptor — wraps every tool call with prevention rules,
        anti-pattern checks, prompt analysis, usage logging, and periodic scans.
        """
        pre_context_parts = []

        # ── PRE-HOOK 1: Execute prevention rules ──
        if name not in EXEMPT_TOOLS:
            try:
                args_text = ' '.join(str(v) for v in (arguments or {}).values() if isinstance(v, str))[:200]
                rule_ctx = {'tool_name': name, 'args_text': args_text}

                # Map tool names to canonical trigger events
                trigger_map = {
                    'record_decision': 'tool.before:record_decision',
                    'set_goal': 'tool.before:set_goal',
                    'record_mistake': 'tool.after:record_mistake',
                    'check_anti_patterns': 'tool.after:check_anti_patterns',
                    'orchestrate_request_tool': 'prompt.received',
                }
                trigger = trigger_map.get(name, f'tool.before:{name}')
                rule_warnings = _execute_prevention_rules(store, trigger, rule_ctx)
                if rule_warnings:
                    pre_context_parts.append(
                        "╔══ 🛡️ PREVENTION RULES FIRED ══╗\n"
                        + "\n".join(rule_warnings)
                        + "\n╚═══════════════════════════════╝"
                    )
            except Exception as e:
                logger.debug(f'Prevention rules pre-hook failed: {e}')

        # ── PRE-HOOK 2: Anti-pattern scan ──
        if name not in EXEMPT_TOOLS:
            try:
                search_terms = name.replace('_', ' ')
                arg_text = ' '.join(str(v) for v in (arguments or {}).values() if isinstance(v, str))
                if arg_text:
                    search_terms += ' ' + arg_text[:200]
                relevant_mistakes = store.check_anti_patterns(search_terms, limit=2)
                if relevant_mistakes:
                    mistake_warns = []
                    for m in relevant_mistakes:
                        mistake_warns.append(
                            f"⚠️ Past mistake: {m['mistake']}\n"
                            f"   Root cause: {m['root_cause']}\n"
                            f"   Fix: {m['fix']}"
                        )
                    pre_context_parts.append(
                        "╔══ ELITE ORCHESTRATOR PRE-CHECK ══╗\n"
                        f"Tool: {name}\n"
                        f"Relevant past mistakes detected:\n\n"
                        + "\n\n".join(mistake_warns)
                        + "\n╚══════════════════════════════════╝"
                    )
            except Exception as e:
                logger.debug(f'Anti-pattern scan failed: {e}')

        # ── PROMPT ANALYSIS: classify intent on orchestration calls ──
        if name == 'orchestrate_request_tool' and arguments:
            try:
                prompt = arguments.get('user_prompt', '')
                if prompt:
                    intent = _classify_intent(prompt)
                    reasoning = _classify_reasoning(prompt)
                    complexity = _classify_complexity(intent, prompt)
                    store.record_prompt_intent(
                        session_id=session_id,
                        prompt_text=prompt[:2000],  # Cap prompt size
                        intent_category=intent,
                        reasoning_type=reasoning
                    )

                    # Classify thinking mode + zoom level (P1)
                    from core.tools.reasoning_amplifier import _classify_thinking_mode, _classify_zoom_level
                    thinking_mode = _classify_thinking_mode(prompt)
                    zoom_level = _classify_zoom_level(prompt)

                    # ── AUTO PRE-FLIGHT: Inject reasoning checklist for complex tasks ──
                    if complexity >= 2:
                        preflight_lines = []
                        preflight_lines.append(
                            f"🛫 REASONING PRE-FLIGHT [Complexity {complexity}/5 | Intent: {intent} | "
                            f"Mode: {thinking_mode} | Zoom: {zoom_level}]\n"
                        )

                        # ── Complexity ≥ 2: Lightweight checks ──
                        if complexity >= 2:
                            if intent in ('debug', 'investigate', 'fix'):
                                preflight_lines.append(
                                    "  🔎 RECOMMENDED: Run `check_anti_patterns` — have I seen this bug before?"
                                )

                        # ── Complexity ≥ 3: Structured reasoning ──
                        if complexity >= 3:
                            preflight_lines.append(
                                "  📝 RECOMMENDED: Use `sequentialthinking` to decompose into steps"
                            )
                            if intent in ('build', 'create'):
                                preflight_lines.append(
                                    "  🔄 RECOMMENDED: Run `adopt_vs_build` — does this already exist?"
                                )
                            if intent in ('build', 'design', 'create'):
                                preflight_lines.append(
                                    "  📋 RECOMMENDED: Run `search_decisions` — check past architectural choices"
                                )
                                preflight_lines.append(
                                    "  📝 AFTER: Run `record_decision` to log your architectural choice"
                                )
                            if intent in ('decide', 'evaluate', 'compare'):
                                preflight_lines.append(
                                    "  📊 RECOMMENDED: Run `calculate_expected_value` — quantify options"
                                )
                                preflight_lines.append(
                                    "  📋 RECOMMENDED: Run `search_decisions` — check past similar decisions"
                                )
                            if intent in ('test', 'experiment', 'verify'):
                                preflight_lines.append(
                                    "  🧪 RECOMMENDED: Run `record_hypothesis` — state your prediction"
                                )
                                preflight_lines.append(
                                    "  📈 AFTER: Run `bayesian_update` to update beliefs with evidence"
                                )
                            if intent == 'deploy':
                                preflight_lines.append(
                                    "  ⚙️ RECOMMENDED: Run `fmea_risk_gate` — quantified risk score"
                                )

                        # ── Complexity ≥ 4: Deep analysis ──
                        if complexity >= 4:
                            preflight_lines.append(
                                "  📚 RECOMMENDED: Run `get_elite_workflow` — load the quality playbook"
                            )
                            if intent in ('build', 'improve'):
                                preflight_lines.append(
                                    "  🔍 RECOMMENDED: Run `fmea_analysis` — what can fail?"
                                )
                                preflight_lines.append(
                                    "  🧠 RECOMMENDED: Run `bias_scan` — check for anchoring"
                                )
                                preflight_lines.append(
                                    "  ✅ AFTER: Run `pre_commit_audit` before delivering code"
                                )
                            if intent == 'deploy':
                                preflight_lines.append(
                                    "  🚦 RECOMMENDED: Create `smoke_test_gate` — capture before state"
                                )
                                preflight_lines.append(
                                    "  🔮 RECOMMENDED: Run `simulate_future_regrets`"
                                )
                                preflight_lines.append(
                                    "  ✅ AFTER: Run `validate_predictions` — did it work as expected?"
                                )
                            if intent in ('debug', 'investigate'):
                                preflight_lines.append(
                                    "  ❓ RECOMMENDED: Run `five_whys` — drill to root cause"
                                )
                                preflight_lines.append(
                                    "  🔍 RECOMMENDED: Run `query_temporal_graph` — check decision history"
                                )
                            if intent == 'audit':
                                preflight_lines.append(
                                    "  🧀 RECOMMENDED: Run `swiss_cheese_audit`"
                                )
                                preflight_lines.append(
                                    "  🔍 RECOMMENDED: Run `query_temporal_graph` — check causal chains"
                                )

                        # ── Complexity 5: Mandatory checks ──
                        if complexity >= 5:
                            preflight_lines.append(
                                "  🏛️ MANDATORY: Run `socratic_challenge` on plan before executing"
                            )
                            preflight_lines.append(
                                "  🎯 MANDATORY: Run `assess_confidence` on final deliverable"
                            )
                            preflight_lines.append(
                                "  📋 MANDATORY: After completion, run `after_action_review`"
                            )

                        pre_context_parts.append("\n".join(preflight_lines))

                    # Execute prompt.received prevention rules (canonical event)
                    prompt_rules = _execute_prevention_rules(
                        store, 'prompt.received', {'tool_name': name, 'args_text': prompt[:200]}
                    )
                    if prompt_rules:
                        pre_context_parts.append(
                            "╔══ 🛡️ PROMPT RULES ══╗\n"
                            + "\n".join(prompt_rules)
                            + "\n╚═════════════════════╝"
                        )
            except Exception as e:
                logger.debug(f'Prompt analysis failed: {e}')

        # ── EXECUTE: run the original tool (timed) ──
        start_time = _time.time()
        result = await _original_call_tool(name, arguments)
        duration_ms = int((_time.time() - start_time) * 1000)

        # ── TOOL USAGE LOG: record every call ──
        try:
            args_summary = str(arguments)[:200] if arguments else ''
            result_text = ''
            if result and hasattr(result, '__iter__'):
                for item in result:
                    if hasattr(item, 'text'):
                        result_text = item.text[:200]
                        break
            store.log_tool_usage(name, args_summary, result_text, session_id, duration_ms)
        except Exception as e:
            logger.debug(f'Tool usage logging failed for {name}: {e}')

        # ── PERIODIC AUTONOMOUS SCAN: every 20 calls ──
        _tool_call_counter[0] += 1
        if _tool_call_counter[0] % 20 == 0:
            try:
                scan = store.autonomous_scan()
                if scan.get('p0_count', 0) > 0:
                    scan_text = f"⚡ AUTONOMOUS SCAN: {scan['p0_count']} P0 gaps detected!\n"
                    for gap in scan.get('gaps', []):
                        if gap['severity'] == 'P0':
                            scan_text += f"  - {gap['detail']}\n"
                    pre_context_parts.insert(0, scan_text)
            except Exception as e:
                logger.debug(f'Periodic autonomous scan failed: {e}')

        # ── POST-HOOK: inject context into result ──
        if pre_context_parts and result:
            try:
                combined = "\n\n".join(pre_context_parts) + "\n\n"
                result_list = list(result)
                if result_list and hasattr(result_list[0], 'text'):
                    result_list[0] = TextContent(
                        type="text",
                        text=combined + result_list[0].text
                    )
                    return result_list
            except Exception as e:
                logger.debug(f'Post-hook result injection failed: {e}')

        return result

    # ── MONKEY-PATCH: replace call_tool ──
    mcp.call_tool = _intercepted_call_tool
    try:
        mcp._mcp_server._handlers['tools/call'] = _intercepted_call_tool
    except Exception as e:
        logger.debug(f'Handler registration for tools/call failed: {e}')


def main():
    import os
    brain_dir = os.environ.get('ELITE_BRAIN_DIR', os.path.expanduser("~/.elite-reasoning/brain"))
    server = create_mcp_server(brain_dir)
    server.run()


if __name__ == "__main__":
    main()
