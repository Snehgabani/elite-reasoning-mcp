"""
Elite Orchestrator — Dynamic MCP & Skill Router

Scans the CURRENT user's IDE environment to discover installed MCP servers
and Skills, then maps the user's intent to the optimal tool combination.

PORTABLE: Uses $HOME-relative paths so every user gets their own
personalized orchestration based on THEIR installed tools.
"""
import os
import json
import requests
from typing import Dict, Any, Optional


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
    Respects per-user preferences: disabled/priority MCPs and skills.
    """
    mcp_dir, skills_dir = _resolve_user_paths()
    mcps = scan_available_mcps(mcp_dir)
    skills = scan_available_skills(skills_dir)
    user_id = _get_user_identity()

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
                return _llm_orchestration(user_prompt, mcps, skills, user_id, api_key)
            except Exception as e:
                return _heuristic_orchestration(user_prompt, mcps, skills, user_id, f"LLM fallback: {e}")
    
    return _heuristic_orchestration(user_prompt, mcps, skills, user_id, "Heuristic mode")


def _llm_orchestration(user_prompt: str, mcps: list[str], skills: list[str], user_id: str, api_key: str) -> str:
    """Use Gemini to generate a smart, personalized orchestration plan."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
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
    
    response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=15)
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _heuristic_orchestration(user_prompt: str, mcps: list[str], skills: list[str], user_id: str, reason: str = "") -> str:
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
    plan = f"# Elite Orchestrator Plan\n\n"
    plan += f"**User:** `{user_id}` | **Mode:** Heuristic ({reason})\n\n"
    plan += f"## Environment\n- **{len(mcps)}** MCP servers installed\n- **{len(skills)}** Skills available\n\n"
    
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
    
    return plan


def register(mcp, store):
    """Register orchestration tools with the MCP server."""
    
    @mcp.tool()
    def orchestrate_request_tool(user_prompt: str) -> str:
        """
        Analyzes the user's request and dynamically routes it to the most relevant
        MCP servers and Skills installed in THIS user's IDE environment.
        Returns a structured Execution Plan. Call at the very start of complex requests.
        """
        return orchestrate_request(user_prompt)
