"""
Elite Orchestrator — Dynamic MCP & Skill Router

Scans the CURRENT user's IDE environment to discover installed MCP servers
and Skills, then maps the user's intent to the optimal tool combination.

PORTABLE: Uses $HOME-relative paths so every user gets their own
personalized orchestration based on THEIR installed tools.
"""
import json as _json
import logging
import os
import urllib.request
from typing import Optional

from core.eval.open_source_integrations import integrations_markdown
from core.eval.outcome_runner import elite_eval_suite_markdown
from core.eval.research_benchmarks import (
    benchmark_catalog_markdown,
    budget_policy_markdown,
    recommend_budget_tier,
    scorecard_markdown,
)
from core.orchestration.capabilities import build_capability_registry, format_capability_report
from core.reasoning.experiment_tree import experiment_tree_markdown
from core.reasoning.nuclear_prompt import nuclear_prompt_markdown, protocol_recommendation_markdown

logger = logging.getLogger(__name__)

# Module-level polisher instance (set by register())
_polisher = None


def _resolve_user_paths() -> tuple[str, str]:
    """
    Discover MCP and Skill directories for the CURRENT user.
    Supports multiple IDE layouts via environment variables or convention.
    """
    home = os.path.expanduser("~")

    # Allow explicit override via environment variables
    mcp_dir = os.environ.get("ELITE_MCP_DIR")
    skills_dir = os.environ.get("ELITE_SKILLS_DIR")

    if not mcp_dir:
        # Auto-detect: try common IDE layouts
        candidates = [
            os.path.join(home, ".gemini", "antigravity", "mcp"),      # Antigravity IDE
            os.path.join(home, ".gemini", "mcp"),                      # Gemini CLI
            os.path.join(home, ".vscode", "mcp"),                      # VS Code
            os.path.join(home, ".cursor", "mcp"),                      # Cursor
        ]
        for c in candidates:
            if os.path.isdir(c):
                mcp_dir = c
                break
        if not mcp_dir:
            mcp_dir = candidates[0]  # Default to Antigravity

    if not skills_dir:
        candidates = [
            os.path.join(home, ".gemini", "config", "plugins"),        # Antigravity IDE
            os.path.join(home, ".gemini", "plugins"),                   # Gemini CLI
        ]
        for c in candidates:
            if os.path.isdir(c):
                skills_dir = c
                break
        if not skills_dir:
            skills_dir = candidates[0]

    return mcp_dir, skills_dir


def _get_user_identity() -> str:
    """Return a stable user identifier for sync namespacing."""
    # Priority: explicit env var > system username > hostname
    user_id = os.environ.get("ELITE_USER_ID")
    if user_id:
        return user_id
    import getpass
    return getpass.getuser()


def scan_available_mcps(mcp_dir: Optional[str] = None) -> list[str]:
    """Scan the user's MCP directory for installed servers."""
    if not mcp_dir:
        mcp_dir, _ = _resolve_user_paths()
    mcps = []
    if os.path.exists(mcp_dir):
        for name in sorted(os.listdir(mcp_dir)):
            if os.path.isdir(os.path.join(mcp_dir, name)):
                mcps.append(name)
    return mcps


def scan_available_skills(skills_dir: Optional[str] = None) -> list[str]:
    """Scan the user's plugins directory for installed skills."""
    if not skills_dir:
        _, skills_dir = _resolve_user_paths()
    skills = []
    if os.path.exists(skills_dir):
        for plugin in sorted(os.listdir(skills_dir)):
            plugin_skills_path = os.path.join(skills_dir, plugin, "skills")
            if os.path.isdir(plugin_skills_path):
                for skill in sorted(os.listdir(plugin_skills_path)):
                    if os.path.isdir(os.path.join(plugin_skills_path, skill)):
                        skills.append(skill)
    return skills


def scan_mcp_tool_schemas(mcp_dir: Optional[str] = None) -> dict[str, list[str]]:
    """
    For each installed MCP, read its tool schema files to get actual tool names.
    Returns {mcp_name: [tool_name_1, tool_name_2, ...]}.
    """
    if not mcp_dir:
        mcp_dir, _ = _resolve_user_paths()
    mcp_tools = {}
    if os.path.exists(mcp_dir):
        for mcp_name in sorted(os.listdir(mcp_dir)):
            mcp_path = os.path.join(mcp_dir, mcp_name)
            if os.path.isdir(mcp_path):
                tools = []
                for f in os.listdir(mcp_path):
                    if f.endswith(".json"):
                        tools.append(f.replace(".json", ""))
                mcp_tools[mcp_name] = tools
    return mcp_tools


def orchestrate_request(user_prompt: str) -> str:
    """
    Analyzes the user's request and dynamically routes it to the most
    relevant MCP servers and Skills installed in THIS user's environment.
    Now includes Goal-Aligned Prompt Polishing for maximum output quality.
    Respects per-user preferences: disabled/priority MCPs and skills.

    Elite upgrade: route from a capability registry that prefers what the
    active IDE can expose (e.g. Zed context_servers) over cross-IDE folders.
    """
    global _polisher
    registry = build_capability_registry()
    mcps = registry.names("mcp")
    skills = registry.names("skill")
    user_id = _get_user_identity()

    # ── Goal-Aligned Prompt Polishing ──────────────────────
    polish_result = None
    if _polisher is not None:
        try:
            polish_result = _polisher.polish(user_prompt)
            logger.debug(
                f"Prompt polished: {polish_result.original_score} → {polish_result.polished_score} "
                f"(+{polish_result.polished_score - polish_result.original_score})"
            )
            # Record the prompt intent and scores for the optimization loop
            import uuid
            session_id = str(uuid.uuid4())
            _polisher._store.record_prompt_intent(
                session_id=session_id,
                prompt_text=user_prompt,
                intent=polish_result.intent,
                original_score=polish_result.original_score,
                polished_score=polish_result.polished_score,
                complexity_score=polish_result.complexity,
                enhancements_applied=polish_result.enhancements_applied
            )
        except Exception as e:
            logger.debug(f"Prompt polishing failed (non-fatal): {e}")

    # Load user profile for personalization
    try:
        from core.identity.user_profile import UserProfile
        profile = UserProfile()

        # Filter out disabled MCPs/Skills
        disabled_mcps = set(profile.disabled_mcps)
        disabled_skills = set(profile.disabled_skills)
        mcps = [m for m in mcps if m not in disabled_mcps]
        skills = [s for s in skills if s not in disabled_skills]

        # Get user's preferred API key
        api_key = (
            os.environ.get("GEMINI_API_KEY")
            or profile.config.get("orchestration", {}).get("gemini_api_key", "")
        )
        orch_mode = profile.orchestration_mode
    except Exception:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        orch_mode = "auto"

    if orch_mode == "llm" or (orch_mode == "auto" and api_key):
        if api_key:
            try:
                plan = _llm_orchestration(user_prompt, mcps, skills, user_id, api_key)
                return _append_elite_metadata(plan, user_prompt, registry.active_ide, registry.warnings, polish_result)
            except Exception as e:
                return _heuristic_orchestration(
                    user_prompt, mcps, skills, user_id,
                    f"LLM fallback: {e}",
                    active_ide=registry.active_ide,
                    capability_warnings=registry.warnings,
                    polish_result=polish_result
                )

    return _heuristic_orchestration(
        user_prompt, mcps, skills, user_id, "Heuristic mode",
        active_ide=registry.active_ide,
        capability_warnings=registry.warnings,
        polish_result=polish_result
    )


def _llm_orchestration(user_prompt: str, mcps: list[str], skills: list[str], user_id: str, api_key: str) -> str:
    """Use Gemini to generate a smart, personalized orchestration plan."""
    base_url = os.environ.get(
        'ELITE_GEMINI_BASE_URL',
        'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'
    )
    url = f"{base_url}?key={api_key}"

    system_instruction = (
        "You are the Elite Orchestrator for an AI coding assistant. "
        "Your job is to read the user's prompt and select the BEST tools from their personally installed MCP servers and Skills. "
        "Return a detailed Markdown Execution Plan detailing exactly which MCPs and Skills to use, and step-by-step how to approach the problem. "
        "Always include 'elite-reasoning' MCP for quality tracking. Provide maximum leverage."
    )

    prompt = (
        f"User: {user_id}\n"
        f"Available MCPs ({len(mcps)}): {', '.join(mcps)}\n"
        f"Available Skills ({len(skills)}): {', '.join(skills)}\n\n"
        f"User Request: {user_prompt}"
    )

    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"parts": [{"text": prompt}]}]
    }

    req = urllib.request.Request(
        url,
        data=_json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = _json.loads(resp.read())
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _append_elite_metadata(plan: str, user_prompt: str, active_ide: str, capability_warnings: tuple[str, ...], polish_result=None) -> str:
    """Append deterministic guardrails to LLM-generated plans."""
    policy = recommend_budget_tier(user_prompt)
    extra = [
        "",
        "## Capability & ROI Guardrails",
        f"- Active IDE: `{active_ide or 'unknown'}`",
        f"- Budget tier: `{policy.tier}` ({policy.max_tool_calls} tool calls, {policy.max_latency_ms} ms target)",
    ]
    for warning in capability_warnings:
        extra.append(f"- ⚠️ {warning}")
    extra.append("- Do not use recommended tools unless the current client exposes them as callable MCP tools.")
    
    plan = plan.rstrip() + "\n" + "\n".join(extra) + "\n"
    
    # ── Quality Directives (from polisher) ──
    if polish_result is not None and polish_result.enhancements_applied:
        plan += "\n## Quality Directives\n"
        plan += "_Auto-injected by the Goal-Aligned Prompt Polisher:_\n\n"
        # Extract just the directive text from the polished prompt
        if "## Quality Directives" in polish_result.polished_prompt:
            directives_section = polish_result.polished_prompt.split("## Quality Directives")[1]
            if "## Output Standard" in directives_section:
                directives_section = directives_section.split("## Output Standard")[0]
            plan += directives_section.strip() + "\n"

    # ── Output Standard (from polisher) ──
    if polish_result is not None and "## Output Standard" in polish_result.polished_prompt:
        standard = polish_result.polished_prompt.split("## Output Standard")[1].strip()
        plan += f"\n## Output Standard\n{standard}\n"

    return plan


def _heuristic_orchestration(
    user_prompt: str,
    mcps: list[str],
    skills: list[str],
    user_id: str,
    reason: str = "",
    active_ide: str = "",
    capability_warnings: tuple[str, ...] = (),
    polish_result=None
) -> str:
    """Keyword-based routing when no LLM is available."""
    prompt_lower = user_prompt.lower()

    selected_mcps = set()
    selected_skills = set()

    # ── Database & Data Layer ──────────────────────────────────
    if any(kw in prompt_lower for kw in ["postgres", "sql", "database", "query", "schema", "migration"]):
        for m in ["alloydb-postgres-admin", "cloud-sql-postgresql-admin", "cloud-sql-managed-mcp", "cloud-sql-mysql-admin", "cloud-sql-sqlserver-admin", "mcp-server-neon"]:
            if m in mcps: selected_mcps.add(m)
        if "prisma-mcp-server" in mcps: selected_mcps.add("prisma-mcp-server")

    if any(kw in prompt_lower for kw in ["firebase", "firestore", "realtime database"]):
        for m in ["firebase-mcp-server", "google-cloud-firestore"]:
            if m in mcps: selected_mcps.add(m)
        for s in ["firebase-firestore", "firebase-basics", "firebase-auth-basics", "firebase-security-rules-auditor"]:
            if s in skills: selected_skills.add(s)

    if "supabase" in prompt_lower:
        if "supabase" in mcps: selected_mcps.add("supabase")

    if any(kw in prompt_lower for kw in ["clickhouse", "analytics", "olap"]):
        if "clickhouse" in mcps: selected_mcps.add("clickhouse")

    if any(kw in prompt_lower for kw in ["kafka", "streaming", "event stream", "pubsub", "pub/sub"]):
        for m in ["google-managed-service-for-apache-kafka", "google-cloud-pubsub"]:
            if m in mcps: selected_mcps.add(m)

    # ── Source Control & CI/CD ─────────────────────────────────
    if any(kw in prompt_lower for kw in ["github", "pull request", "pr ", "commit", "branch", "merge", "issue"]):
        if "mcp-server-github" in mcps: selected_mcps.add("mcp-server-github")
        for s in ["github-pr-workflow", "github-code-review", "github-issues", "github-repo-management", "github-auth"]:
            if s in skills: selected_skills.add(s)

    if any(kw in prompt_lower for kw in ["linear", "ticket", "sprint", "backlog"]):
        if "linear-mcp-server" in mcps: selected_mcps.add("linear-mcp-server")

    if any(kw in prompt_lower for kw in ["jira", "confluence", "atlassian"]):
        if "atlassian-mcp-server" in mcps: selected_mcps.add("atlassian-mcp-server")

    # ── Frontend & Design ──────────────────────────────────────
    if any(kw in prompt_lower for kw in ["react", "frontend", "ui", "dashboard", "landing page", "website", "component", "css", "html", "design"]):
        for s in ["frontend-design", "popular-web-designs", "sketch", "p5js"]:
            if s in skills: selected_skills.add(s)

    # ── Cloud Infrastructure ───────────────────────────────────
    if any(kw in prompt_lower for kw in ["cloud run", "deploy", "container", "docker", "serverless"]):
        if "cloudrun" in mcps: selected_mcps.add("cloudrun")
        if "deploy-fullstack-vercel" in skills: selected_skills.add("deploy-fullstack-vercel")

    if any(kw in prompt_lower for kw in ["compute", "vm", "instance", "gce", "virtual machine"]):
        if "google-compute-engine" in mcps: selected_mcps.add("google-compute-engine")

    if any(kw in prompt_lower for kw in ["logging", "logs", "error log"]):
        if "google-cloud-logging" in mcps: selected_mcps.add("google-cloud-logging")

    if any(kw in prompt_lower for kw in ["monitoring", "alert", "metric"]):
        if "google-cloud-monitoring" in mcps: selected_mcps.add("google-cloud-monitoring")

    if any(kw in prompt_lower for kw in ["bigtable", "wide column"]):
        if "google-cloud-bigtable-admin" in mcps: selected_mcps.add("google-cloud-bigtable-admin")

    # ── Communication & Messaging ──────────────────────────────
    if any(kw in prompt_lower for kw in ["slack", "channel", "workspace message"]):
        for s in ["slack", "slack-app-setup"]:
            if s in skills: selected_skills.add(s)

    if any(kw in prompt_lower for kw in ["email", "gmail", "inbox", "send email"]):
        for s in ["gmail", "outlook", "inbox-management"]:
            if s in skills: selected_skills.add(s)

    if any(kw in prompt_lower for kw in ["discord", "bot"]):
        if "discord-app-setup" in skills: selected_skills.add("discord-app-setup")

    # ── Debugging & Quality ────────────────────────────────────
    if any(kw in prompt_lower for kw in ["debug", "error", "crash", "fix", "bug", "broken"]):
        for s in ["systematic-debugging", "chrome-devtools", "memory-leak-debugging", "python-debugpy"]:
            if s in skills: selected_skills.add(s)

    if any(kw in prompt_lower for kw in ["test", "tdd", "unit test", "coverage"]):
        for s in ["test-driven-development", "code-quality-auditor"]:
            if s in skills: selected_skills.add(s)

    if any(kw in prompt_lower for kw in ["review", "audit", "security"]):
        for s in ["requesting-code-review", "adversarial-reviewer", "code-quality-auditor"]:
            if s in skills: selected_skills.add(s)

    # ── Research & Knowledge ───────────────────────────────────
    if any(kw in prompt_lower for kw in ["research", "paper", "arxiv", "literature"]):
        for s in ["research-router", "arxiv", "literature-search-arxiv"]:
            if s in skills: selected_skills.add(s)

    if any(kw in prompt_lower for kw in ["notion", "note", "documentation"]):
        for s in ["notion", "obsidian", "document-writer"]:
            if s in skills: selected_skills.add(s)

    # ── Android & Mobile ───────────────────────────────────────
    if any(kw in prompt_lower for kw in ["android", "mobile", "apk", "kotlin"]):
        if "android-cli" in skills: selected_skills.add("android-cli")
        if "android-management-api" in mcps: selected_mcps.add("android-management-api")

    # ── AI/ML & LLMs ──────────────────────────────────────────
    if any(kw in prompt_lower for kw in ["model", "llm", "fine-tune", "training", "inference", "huggingface", "weights"]):
        for s in ["huggingface-hub", "weights-and-biases", "serving-llms-vllm", "llama-cpp"]:
            if s in skills: selected_skills.add(s)

    # ── Documentation & Knowledge Grounding ─────────────────
    if any(kw in prompt_lower for kw in ["firebase", "flutter", "android", "gcloud", "vertex", "google cloud", "google ai", "dart", "google maps", "cloud run"]):
        if "google-developer-knowledge" in mcps: selected_mcps.add("google-developer-knowledge")

    if any(kw in prompt_lower for kw in ["library", "package", "npm", "pip", "docs", "documentation", "api reference", "sdk"]):
        if "context7" in mcps: selected_mcps.add("context7")

    if any(kw in prompt_lower for kw in ["remember", "memory", "knowledge", "history", "past decision", "what did i", "last time"]):
        if "mcp-server-memory" in mcps: selected_mcps.add("mcp-server-memory")

    # ── Reasoning & Thinking ───────────────────────────────
    if any(kw in prompt_lower for kw in ["think through", "step by step", "reason", "analyze deeply", "break down"]):
        if "sequential-thinking" in mcps: selected_mcps.add("sequential-thinking")

    # ── Always include Elite Reasoning ─────────────────────────
    if "elite-reasoning" in mcps:
        selected_mcps.add("elite-reasoning")

    # ── Build the plan ─────────────────────────────────────────
    plan = "# Elite Orchestrator Plan\n\n"
    policy = recommend_budget_tier(user_prompt)
    plan += f"**User:** `{user_id}` | **Mode:** Heuristic ({reason})\n\n"
    plan += "## Environment\n"
    plan += f"- **Active IDE:** `{active_ide or 'unknown'}`\n"
    plan += f"- **Recommendable MCP servers:** {len(mcps)}\n"
    plan += f"- **Recommendable Skills:** {len(skills)}\n"
    plan += f"- **ROI budget tier:** `{policy.tier}` — max {policy.max_tool_calls} tool calls / {policy.max_latency_ms} ms target\n"
    if capability_warnings:
        for warning in capability_warnings:
            plan += f"- ⚠️ {warning}\n"
    plan += "\n"

    # ── Prompt Quality & Goal Alignment Section ──
    if polish_result is not None:
        plan += "## 📊 Prompt Quality\n"
        plan += "| Metric | Value |\n|--------|-------|\n"
        plan += f"| Original Score | {polish_result.original_score}/100 |\n"
        plan += f"| Polished Score | {polish_result.polished_score}/100 |\n"
        plan += f"| Improvement | +{polish_result.polished_score - polish_result.original_score} |\n"
        plan += f"| Complexity | {polish_result.complexity}/5 |\n"
        plan += f"| Intent | {polish_result.intent} |\n\n"

        if polish_result.goals_aligned:
            plan += "### 🎯 Goals Aligned\n"
            for g in polish_result.goals_aligned:
                plan += f"- {g}\n"
            plan += "\n"

        if polish_result.enhancements_applied:
            plan += "### ✨ Enhancements Applied\n"
            for e in polish_result.enhancements_applied:
                plan += f"- `{e}`\n"
            plan += "\n"

    plan += "## Recommended MCPs\n"
    if selected_mcps:
        for m in sorted(selected_mcps):
            plan += f"- `{m}`\n"
    else:
        plan += "- None specifically matched. Use general-purpose tools.\n"

    plan += "\n## Recommended Skills\n"
    if selected_skills:
        for s in sorted(selected_skills):
            plan += f"- `{s}`\n"
    else:
        plan += "- None specifically matched. Proceed with standard approach.\n"

    plan += "\n## Execution Strategy\n"
    plan += "1. **Load Skills** — Read the SKILL.md instructions for each recommended skill above.\n"
    plan += "2. **Gather Context** — Use the recommended MCP tools to query/scan relevant infrastructure.\n"
    plan += "3. **Execute** — Fulfill the user's request using the discovered leverage.\n"
    plan += "4. **Verify** — Run quality checks and record decisions via `elite-reasoning` MCP.\n"
    plan += (
        "5. **ROI Gate** — Stay within the recommended tool budget unless risk or uncertainty justifies escalation.\n"
    )
    plan += "\n## Evidence / Benchmark Guidance\n"
    if any(kw in prompt_lower for kw in ["research", "paper", "benchmark", "evidence", "model", "quality", "roi"]):
        plan += "- Use research-backed metrics: task success, regression prevention, tool efficiency, evidence quality, calibration, latency/cost ROI, and robustness.\n"
        plan += "- Prefer SWE-bench-style executable validation for coding-agent changes and API-Bank/ToolBench-style metrics for tool routing.\n"
        plan += "- For model/framework adoption, call `recommend_open_source_integrations` and keep heavy frameworks optional until evals justify them.\n"
    else:
        plan += "- Use executable validation where available; record confidence only when making predictions or recommendations.\n"

    if any(kw in prompt_lower for kw in ["think", "reason", "break down", "loop", "experiment", "stress", "top tier"]):
        plan += "- For deep work, start with `nuclear_prompt_breakdown`, choose a protocol with `select_reasoning_protocol`, then branch with `build_experiment_tree` when complexity is high.\n"
    if any(kw in prompt_lower for kw in ["eval", "evaluate", "score", "quality", "benchmark", "regression"]):
        plan += "- Use `run_elite_eval_suite` as a cheap local smoke gate before heavier external eval frameworks.\n"

    # ── Quality Directives (from polisher) ──
    if polish_result is not None and polish_result.enhancements_applied:
        plan += "\n## Quality Directives\n"
        plan += "_Auto-injected by the Goal-Aligned Prompt Polisher:_\n\n"
        # Extract just the directive text from the polished prompt
        if "## Quality Directives" in polish_result.polished_prompt:
            directives_section = polish_result.polished_prompt.split("## Quality Directives")[1]
            if "## Output Standard" in directives_section:
                directives_section = directives_section.split("## Output Standard")[0]
            plan += directives_section.strip() + "\n"

    # ── Output Standard (from polisher) ──
    if polish_result is not None and "## Output Standard" in polish_result.polished_prompt:
        standard = polish_result.polished_prompt.split("## Output Standard")[1].strip()
        plan += f"\n## Output Standard\n{standard}\n"

    return plan


def register(mcp, store):
    """Register orchestration tools with the MCP server."""
    global _polisher

    # Initialize the prompt polisher with store access
    try:
        from core.tools.goal_prompt_polisher import GoalPromptPolisher
        _polisher = GoalPromptPolisher(store)
        logger.info("GoalPromptPolisher initialized for orchestration")
    except Exception as e:
        logger.debug(f"GoalPromptPolisher not available: {e}")
        _polisher = None

    @mcp.tool()
    def orchestrate_request_tool(user_prompt: str) -> str:
        """
        Analyzes the user's request and dynamically routes it to the most relevant
        MCP servers and Skills installed in THIS user's IDE environment.
        Now includes Goal-Aligned Prompt Polishing for maximum output quality.
        Returns a structured Execution Plan with quality directives and goal alignment.
        Call at the very start of complex requests.
        """
        return orchestrate_request(user_prompt)

    @mcp.tool()
    def verify_capabilities_tool() -> str:
        """
        Verify which MCP servers and skills are actually recommendable for the active IDE.
        Use before relying on optional tools or cross-IDE skills.
        """
        return format_capability_report(build_capability_registry())

    @mcp.tool()
    def research_benchmark_catalog(task_class: str = "") -> str:
        """
        Return a research-backed benchmark catalog for evaluating reasoning, coding,
        tool use, research grounding, calibration, and ROI.
        Args:
            task_class: Optional filter such as coding_agent, tool_use, calibration, research_grounding.
        """
        return benchmark_catalog_markdown(task_class)

    @mcp.tool()
    def elite_outcome_scorecard() -> str:
        """
        Return the weighted Elite scorecard used to measure whether reasoning tools
        improved outcomes instead of merely adding process.
        """
        return scorecard_markdown()

    @mcp.tool()
    def roi_tool_budget(prompt: str = "", complexity: int = 0) -> str:
        """
        Recommend a reasoning/tool-call budget based on risk and complexity.
        Use this to prevent tool theater and keep quality improvements ROI-positive.
        """
        return budget_policy_markdown(prompt, complexity)

    @mcp.tool()
    def nuclear_prompt_breakdown(prompt: str) -> str:
        """
        Decompose a prompt into explicit requirements, implicit requirements,
        constraints, risks, evidence needs, success criteria, validation plan,
        allowed tools, and stop conditions. Works without external LLM calls.
        """
        return nuclear_prompt_markdown(prompt)

    @mcp.tool()
    def select_reasoning_protocol(prompt: str, complexity: int = 0) -> str:
        """
        Select a model-agnostic reasoning protocol stack for a prompt:
        direct, ReAct, Tree-of-Thoughts, Reflexion, Self-Consistency,
        Self-Debugging, or Evidence-Grounded Research.
        """
        return protocol_recommendation_markdown(prompt, complexity)

    @mcp.tool()
    def build_experiment_tree(prompt: str, max_branches: int = 3) -> str:
        """
        Generate a deterministic experiment tree with hypotheses, candidate
        approaches, validation methods, risks, fallbacks, expected observations,
        and stopping criteria.
        """
        return experiment_tree_markdown(prompt, max_branches)

    @mcp.tool()
    def run_elite_eval_suite(scope: str = "smoke") -> str:
        """
        Run the lightweight local Elite eval suite. No external model calls.
        Scores task_success, regression_prevention, tool_efficiency,
        evidence_quality, calibration, latency_cost_roi, and robustness.
        """
        return elite_eval_suite_markdown(scope)

    @mcp.tool()
    def recommend_open_source_integrations(use_case: str = "") -> str:
        """
        Recommend optional open-source integrations for prompt optimization,
        eval/red-team/CI, pytest-native LLM evals, rigorous agent benchmarks,
        and local/open-source model providers without adding core dependencies.
        """
        return integrations_markdown(use_case)
