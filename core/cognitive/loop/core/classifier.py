"""Intent, complexity, and reasoning-type classification.

Research-grounded multi-signal classification that determines which
reasoning scaffolds to activate. Uses weighted keyword signals combined
with structural analysis for more accurate routing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PromptClassification:
    """Complete classification result for a prompt."""
    intent: str
    reasoning_type: str
    complexity: int
    budget_tier: str
    recommended_tools: list[str]
    thinking_mode: str
    zoom_level: str
    risk_signals: list[str]


# ── Intent Classification ────────────────────────────────────

INTENT_SIGNALS: dict[str, tuple[tuple[str, int], ...]] = {
    "debug": (
        ("debug", 3), ("error", 2), ("broken", 2), ("crash", 2), ("bug", 2),
        ("traceback", 3), ("exception", 2), ("not working", 3), ("fix error", 3),
        ("stack trace", 3), ("segfault", 3), ("timeout", 2), ("500", 2),
    ),
    "build": (
        ("build", 2), ("implement", 3), ("add feature", 3), ("create", 2),
        ("new project", 3), ("scaffold", 3), ("generate", 2), ("write code", 3),
        ("set up", 2), ("integrate", 2),
    ),
    "audit": (
        ("audit", 3), ("review", 2), ("check", 2), ("scan", 2),
        ("diagnose", 2), ("health", 2), ("inspect", 2), ("verify", 2),
        ("security review", 3), ("code review", 3),
    ),
    "research": (
        ("research", 3), ("evidence", 2), ("paper", 2), ("benchmark", 2),
        ("citation", 3), ("source", 2), ("state of the art", 3), ("survey", 2),
        ("literature", 3), ("compare approaches", 3),
    ),
    "deploy": (
        ("deploy", 3), ("push", 2), ("release", 2), ("publish", 2),
        ("ship", 2), ("production", 3), ("staging", 2), ("migrate", 3),
    ),
    "design": (
        ("design", 2), ("architect", 3), ("architecture", 3), ("schema", 2),
        ("data model", 3), ("api design", 3), ("system design", 3),
    ),
    "decide": (
        ("decide", 2), ("choose", 2), ("pick", 2), ("which one", 2),
        ("should i", 2), ("trade-off", 3), ("tradeoff", 3), ("vs ", 2),
        ("pros and cons", 3), ("comparison", 2),
    ),
    "optimize": (
        ("optimize", 2), ("improve", 2), ("refactor", 2), ("performance", 2),
        ("faster", 2), ("bottleneck", 3), ("profiling", 3), ("memory leak", 3),
    ),
    "test": (
        ("test", 2), ("spec", 2), ("unittest", 3), ("e2e test", 3),
        ("integration test", 3), ("coverage", 2), ("tdd", 3),
    ),
    "explain": (
        ("explain", 2), ("how does", 2), ("why does", 2), ("what is", 1),
        ("understand", 2), ("show me", 1), ("walk through", 2),
    ),
}


def classify_intent(prompt: str) -> str:
    """Classify the primary intent of a prompt using weighted signals."""
    lower = prompt.lower()
    scores: dict[str, int] = {}
    for intent, signals in INTENT_SIGNALS.items():
        score = sum(weight for keyword, weight in signals if keyword in lower)
        if score > 0:
            scores[intent] = score
    if not scores:
        return "general"
    return max(scores, key=scores.get)


# ── Complexity Classification ────────────────────────────────

COMPLEXITY_SIGNALS = {
    "high": (
        "production", "security", "authentication", "migration",
        "database schema", "breaking change", "backwards compat",
        "scale", "concurrent", "distributed", "microservice",
        "encryption", "compliance", "payment", "billing",
    ),
    "medium": (
        "refactor", "redesign", "architecture", "integrate",
        "api design", "data model", "performance", "optimize",
        "end to end", "full stack", "comprehensive", "multi-file",
    ),
    "low": (
        "typo", "rename", "comment", "format", "lint",
        "simple", "quick", "minor", "small fix", "one line",
    ),
}

COMPLEXITY_INTENT_BOOST = {
    "deploy": 2, "audit": 2, "research": 2, "design": 2,
    "build": 1, "optimize": 1, "debug": 1,
}


def classify_complexity(prompt: str, intent: str) -> int:
    """Classify task complexity on a 1-5 scale.
    
    Combines:
    - Prompt length (longer = more context = more complex)
    - Intent category (deploy/audit = inherently higher risk)
    - Risk signal keywords (production, security, etc.)
    - Structural complexity (multi-file, cross-system)
    """
    lower = prompt.lower()
    score = 1

    # Length signal
    if len(lower) > 600:
        score += 2
    elif len(lower) > 250:
        score += 1

    # Intent signal
    score += COMPLEXITY_INTENT_BOOST.get(intent, 0)

    # Risk keywords
    for kw in COMPLEXITY_SIGNALS["high"]:
        if kw in lower:
            score += 2
            break

    for kw in COMPLEXITY_SIGNALS["medium"]:
        if kw in lower:
            score += 1
            break

    # Trivial dampening
    for kw in COMPLEXITY_SIGNALS["low"]:
        if kw in lower:
            score = max(1, score - 2)
            break

    return min(5, max(1, score))


# ── Reasoning Type Classification ────────────────────────────

def classify_reasoning_type(prompt: str) -> str:
    """Classify the meta-pattern of the prompt.
    
    Detects: loop_kick, depth_escalation, gap_injection,
    frustration, meta_instruction, correction, substantive.
    """
    lower = prompt.lower().strip()

    # Loop kicks (continuation)
    if lower in {"go", "continue", "proceed", "next", "keep going", "yes", "do it", "ok"}:
        return "loop_kick"

    # Depth escalation
    if any(kw in lower for kw in ("think deeper", "more detail", "go deeper", "drill down",
                                    "comprehensive", "thorough", "in depth")):
        return "depth_escalation"

    # Gap injection
    if any(kw in lower for kw in ("also need", "what about", "we must", "don't forget",
                                    "missing", "you forgot", "overlooked")):
        return "gap_injection"

    # Frustration
    if any(kw in lower for kw in ("still", "again", "why not", "already told",
                                    "i said", "still not", "same problem")):
        return "frustration"

    # Meta-instruction
    if any(kw in lower for kw in ("always", "every step", "make sure", "must",
                                    "never", "from now on", "remember to", "rule:")):
        return "meta_instruction"

    # Correction
    if any(kw in lower for kw in ("no,", "not that", "wrong", "incorrect", "i meant")):
        return "correction"

    return "substantive"


# ── Thinking Mode Classification ─────────────────────────────

THINKING_MODES = {
    "convergent": ("fix", "choose", "pick", "select", "solve", "correct", "resolve"),
    "divergent": ("brainstorm", "explore", "what if", "ideas", "possibilities", "creative"),
    "analytical": ("analyze", "audit", "benchmark", "measure", "profile", "diagnose"),
    "critical": ("review", "stress-test", "verify", "challenge", "critique", "risk"),
    "systems": ("architecture", "design system", "scale", "distributed", "pipeline"),
}


def classify_thinking_mode(prompt: str) -> str:
    """Classify the cognitive mode required for this task."""
    lower = prompt.lower()
    scores = {}
    for mode, keywords in THINKING_MODES.items():
        scores[mode] = sum(1 for kw in keywords if kw in lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "convergent"


# ── Zoom Level Classification ────────────────────────────────

ZOOM_LEVELS = {
    "satellite": ("overview", "strategy", "vision", "roadmap", "big picture", "goals"),
    "architecture": ("system design", "architecture", "component", "data flow"),
    "module": ("module", "class", "package", "feature", "controller"),
    "function": ("function", "method", "algorithm", "handler", "endpoint"),
    "line": ("typo", "rename", "format", "lint", "spacing", "syntax"),
}


def classify_zoom_level(prompt: str) -> str:
    """Classify the zoom level: satellite → architecture → module → function → line."""
    lower = prompt.lower()
    for level in ["line", "function", "module", "architecture", "satellite"]:
        if any(kw in lower for kw in ZOOM_LEVELS[level]):
            return level
    return "function"


# ── Risk Signal Detection ────────────────────────────────────

RISK_KEYWORDS = {
    "security": ("auth", "secret", "credential", "token", "password", "injection", "xss"),
    "data_loss": ("delete", "drop", "truncate", "overwrite", "migration", "destructive"),
    "production": ("production", "live", "deploy", "release", "staging"),
    "financial": ("payment", "billing", "charge", "refund", "subscription"),
    "compliance": ("gdpr", "hipaa", "pci", "compliance", "audit trail"),
}


def detect_risk_signals(prompt: str) -> list[str]:
    """Detect risk categories present in the prompt."""
    lower = prompt.lower()
    risks = []
    for category, keywords in RISK_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            risks.append(category)
    return risks


# ── Budget Tier Recommendation ───────────────────────────────

BUDGET_TIERS = {
    "trivial": {"max_tool_calls": 0, "max_latency_ms": 500, "reasoning": "none"},
    "standard": {"max_tool_calls": 3, "max_latency_ms": 4000, "reasoning": "basic"},
    "high_risk": {"max_tool_calls": 6, "max_latency_ms": 12000, "reasoning": "full"},
    "research_grade": {"max_tool_calls": 10, "max_latency_ms": 25000, "reasoning": "exhaustive"},
}


def recommend_budget_tier(complexity: int, risks: list[str]) -> str:
    """Recommend a reasoning/tool budget tier."""
    if complexity >= 5 or len(risks) >= 3:
        return "research_grade"
    if complexity >= 4 or len(risks) >= 2 or "security" in risks or "data_loss" in risks:
        return "high_risk"
    if complexity >= 2:
        return "standard"
    return "trivial"


# ── Tool Recommendation ─────────────────────────────────────

def recommend_tools(intent: str, complexity: int, budget_tier: str) -> list[str]:
    """Recommend which reasoning tools to activate based on classification."""
    tools = []

    if budget_tier == "trivial":
        return tools

    # Standard tier: basic reasoning
    if complexity >= 2:
        tools.append("reasoning_decompose")

    # High risk: add verification
    if complexity >= 3:
        tools.append("reasoning_amplify")

    if complexity >= 4:
        if intent in ("build", "optimize"):
            tools.append("reasoning_amplify")
        if intent in ("decide", "design"):
            tools.append("reasoning_amplify")
        if intent == "deploy":
            tools.append("reasoning_verify")
        if intent == "audit":
            tools.append("reasoning_verify")

    if complexity >= 5:
        tools.append("reasoning_verify")
        tools.append("calibration_log")

    # Deduplicate while preserving order
    seen = set()
    result = []
    for t in tools:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


# ── Full Classification ──────────────────────────────────────

def classify_prompt(prompt: str) -> PromptClassification:
    """Complete prompt classification — the entry point for routing."""
    intent = classify_intent(prompt)
    reasoning_type = classify_reasoning_type(prompt)
    complexity = classify_complexity(prompt, intent)
    risks = detect_risk_signals(prompt)
    budget_tier = recommend_budget_tier(complexity, risks)
    tools = recommend_tools(intent, complexity, budget_tier)
    thinking_mode = classify_thinking_mode(prompt)
    zoom_level = classify_zoom_level(prompt)

    return PromptClassification(
        intent=intent,
        reasoning_type=reasoning_type,
        complexity=complexity,
        budget_tier=budget_tier,
        recommended_tools=tools,
        thinking_mode=thinking_mode,
        zoom_level=zoom_level,
        risk_signals=risks,
    )
