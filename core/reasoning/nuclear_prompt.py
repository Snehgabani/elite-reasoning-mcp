"""Model-agnostic prompt decomposition and reasoning protocol selection.

The goal of this module is to help weaker/local LLMs by making hidden task
structure explicit before they start answering. It intentionally avoids external
LLM calls and heavy dependencies so it can run inside every MCP session.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Literal

ReasoningProtocol = Literal[
    "direct",
    "ReAct",
    "Tree-of-Thoughts",
    "Reflexion",
    "Self-Consistency",
    "Self-Debugging",
    "Evidence-Grounded Research",
]

_CODE_TERMS = (
    "code",
    "repo",
    "repository",
    "test",
    "pytest",
    "ruff",
    "pyright",
    "build",
    "implement",
    "fix",
    "debug",
    "refactor",
    "install",
    "configure",
    "mcp",
    "api",
    "tool",
    "server",
)

_RESEARCH_TERMS = (
    "research",
    "paper",
    "citation",
    "evidence",
    "benchmark",
    "eval",
    "evaluate",
    "compare",
    "quality",
    "truth",
    "hallucination",
    "roi",
)

_RISK_TERMS = (
    "auth",
    "authentication",
    "secret",
    "credential",
    "security",
    "payment",
    "delete",
    "destructive",
    "migration",
    "production",
    "sync",
    "always",
    "everytime",
)

_REQUIREMENT_PATTERNS = (
    "must",
    "need",
    "needed",
    "want",
    "should",
    "do not",
    "don't",
    "avoid",
    "add",
    "create",
    "implement",
    "install",
    "configure",
    "upgrade",
    "fix",
    "run",
    "validate",
    "test",
    "expose",
    "return",
)


@dataclass(frozen=True)
class PromptBreakdown:
    """A structured, JSON-compatible task decomposition."""

    user_goal: str
    explicit_requirements: tuple[str, ...]
    implicit_requirements: tuple[str, ...]
    constraints: tuple[str, ...]
    risk_areas: tuple[str, ...]
    needed_evidence: tuple[str, ...]
    success_criteria: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    validation_plan: tuple[str, ...]
    stop_conditions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProtocolRecommendation:
    """Recommended reasoning protocol stack for a prompt."""

    selected_protocol: ReasoningProtocol
    supporting_protocols: tuple[ReasoningProtocol, ...]
    rationale: tuple[str, ...]
    execution_steps: tuple[str, ...]
    escalation_triggers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _split_units(prompt: str) -> list[str]:
    normalized = prompt.replace("\r", "\n")
    raw_units: list[str] = []
    for line in normalized.split("\n"):
        line = line.strip(" -\t")
        if not line:
            continue
        raw_units.extend(re.split(r"(?<=[.!?;])\s+", line))
    units = [_clean(unit.strip(" -*\t")) for unit in raw_units if _clean(unit.strip(" -*\t"))]
    return units or [_clean(prompt)]


def _dedupe(items: list[str], limit: int | None = None) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = _clean(item).strip(" .")
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if limit and len(result) >= limit:
            break
    return tuple(result)


def _goal_from_prompt(prompt: str, units: list[str]) -> str:
    goal_terms = ("goal", "want", "need", "implement", "upgrade", "fix", "configure", "build", "improve", "make")
    for unit in units:
        if any(term in unit.lower() for term in goal_terms):
            return unit[:260]
    return units[0][:260]


def _explicit_requirements(prompt: str, units: list[str]) -> tuple[str, ...]:
    requirements = [unit for unit in units if any(pattern in unit.lower() for pattern in _REQUIREMENT_PATTERNS)]

    bullet_like = re.findall(r"(?:^|\n)\s*[-*]\s+([^\n]+)", prompt)
    requirements.extend(_clean(item) for item in bullet_like)

    if not requirements:
        requirements = [units[0]]
    return _dedupe(requirements, limit=10)


def _implicit_requirements(prompt: str) -> tuple[str, ...]:
    requirements = [
        "Preserve existing user work and avoid unrelated changes.",
        "Prefer the smallest implementation that satisfies the stated goal.",
    ]
    if _contains_any(prompt, _CODE_TERMS):
        requirements.extend(
            [
                "Inspect existing patterns before editing code.",
                "Run the most relevant tests or validation commands available.",
                "Report validation honestly, including known baseline failures.",
            ]
        )
    if _contains_any(prompt, _RESEARCH_TERMS):
        requirements.extend(
            [
                "Separate evidence-backed claims from assumptions.",
                "Use benchmark-style outcome metrics instead of process-only claims.",
            ]
        )
    if any(term in prompt.lower() for term in ("weak", "opensource", "open-source", "lower quality", "local model")):
        requirements.append("Make the scaffold deterministic and model-agnostic so weaker/local LLMs can follow it.")
    if any(term in prompt.lower() for term in ("mcp", "tool", "inside you", "zed")):
        requirements.append("Verify the tool is exposed in the active client before relying on it.")
    return _dedupe(requirements)


def _constraints(prompt: str) -> tuple[str, ...]:
    constraints = []
    lower = prompt.lower()
    if _contains_any(prompt, _CODE_TERMS):
        constraints.append("Follow existing repository style, packaging, and test conventions.")
    if any(term in lower for term in ("no hard", "optional", "free", "opensource", "open-source", "dependency")):
        constraints.append(
            "Keep heavy external frameworks optional; do not add mandatory dependencies unless justified."
        )
    if _contains_any(prompt, _RISK_TERMS):
        constraints.append(
            "Treat security, sync, and irreversible actions as high-risk and fail closed where practical."
        )
    if "fable" in lower or "claude" in lower:
        constraints.append("Do not claim unavailable proprietary models are installed or accessible.")
    if any(term in lower for term in ("roi", "latency", "cost", "tool calls")):
        constraints.append("Budget reasoning/tool usage so quality gains justify added latency and complexity.")
    if not constraints:
        constraints.append("Ask for clarification only when missing information would make progress unsafe.")
    return tuple(constraints)


def _risk_areas(prompt: str) -> tuple[str, ...]:
    risks = []
    if _contains_any(prompt, _CODE_TERMS):
        risks.extend(
            [
                "Tool registration or packaging changes may silently fail until the MCP is reinstalled/restarted.",
                "New heuristics can overfit happy-path prompts and degrade ambiguous requests.",
                "Tests may pass locally while installed MCP code remains stale.",
            ]
        )
    if _contains_any(prompt, _RESEARCH_TERMS):
        risks.extend(
            [
                "Research claims can become stale or unsupported without evidence checks.",
                "More reasoning process can create tool theater if outcome quality is not measured.",
            ]
        )
    if _contains_any(prompt, _RISK_TERMS):
        risks.append("Security/sync mistakes can create unauthorized access, data leakage, or persistent bad state.")
    if not risks:
        risks.append("The answer may solve the visible request while missing implicit success criteria.")
    return _dedupe(risks)


def _needed_evidence(prompt: str) -> tuple[str, ...]:
    evidence = []
    if _contains_any(prompt, _CODE_TERMS):
        evidence.extend(
            [
                "Relevant repository files and existing implementation patterns.",
                "Targeted tests, lint checks, or import/smoke validation.",
            ]
        )
    if _contains_any(prompt, _RESEARCH_TERMS):
        evidence.extend(
            [
                "Benchmark families and metrics aligned to the task class.",
                "Source-backed claims with contradiction/uncertainty handling.",
            ]
        )
    if any(term in prompt.lower() for term in ("install", "configure", "mcp", "tool")):
        evidence.append("Capability verification that the active IDE/client exposes the expected MCP tools.")
    if not evidence:
        evidence.append("User-provided requirements and direct consistency checks against the final answer.")
    return _dedupe(evidence)


def _success_criteria(prompt: str) -> tuple[str, ...]:
    criteria = ["The final result directly satisfies the user goal and explicit requirements."]
    if _contains_any(prompt, _CODE_TERMS):
        criteria.extend(
            [
                "Relevant tests or validation commands pass, or remaining failures are clearly identified as baseline/unrelated.",
                "Changes are minimal, focused, and exposed through the expected MCP/client surface.",
            ]
        )
    if _contains_any(prompt, _RESEARCH_TERMS):
        criteria.append("Claims are tied to benchmarks/evidence and uncertainty is explicit.")
    if any(term in prompt.lower() for term in ("weak", "opensource", "open-source", "lower quality")):
        criteria.append(
            "The output gives weaker models a concrete step structure, validation checks, and stop conditions."
        )
    return _dedupe(criteria)


def _allowed_tools(prompt: str) -> tuple[str, ...]:
    tools = []
    if _contains_any(prompt, _CODE_TERMS):
        tools.extend(("file_search", "read_file", "edit/write_file", "terminal_test_or_lint", "diagnostics"))
    if _contains_any(prompt, _RESEARCH_TERMS):
        tools.extend(("benchmark_catalog", "web_or_doc_search_when_current_evidence_is_needed", "confidence_audit"))
    if any(term in prompt.lower() for term in ("mcp", "tool", "zed", "install", "configure")):
        tools.extend(("orchestrator", "capability_verification", "installed_tool_smoke_test"))
    if not tools:
        tools.append("direct_answer")
    return _dedupe(tools)


def _validation_plan(prompt: str) -> tuple[str, ...]:
    plan = []
    if _contains_any(prompt, _CODE_TERMS):
        plan.extend(
            [
                "Run targeted tests closest to the changed code.",
                "Run repository lint/static checks configured for the project.",
                "Smoke-test installed/runtime imports when packaging or MCP exposure changes.",
            ]
        )
    if _contains_any(prompt, _RESEARCH_TERMS):
        plan.extend(
            [
                "Check that each major claim maps to a benchmark, source, or explicitly labeled assumption.",
                "Use outcome scorecard dimensions to avoid process-only success claims.",
            ]
        )
    if not plan:
        plan.append("Compare final answer against explicit requirements and stop conditions.")
    return _dedupe(plan)


def _stop_conditions(prompt: str) -> tuple[str, ...]:
    conditions = ["All explicit requirements are addressed or a blocker is named with the next concrete step."]
    if _contains_any(prompt, _CODE_TERMS):
        conditions.append("Validation has passed, or failures are reproducible and not caused by the current change.")
    if _contains_any(prompt, _RESEARCH_TERMS):
        conditions.append("Evidence is sufficient for the claim strength, with uncertainty called out where needed.")
    conditions.append("No additional tool use is likely to change the answer enough to justify its cost.")
    return tuple(conditions)


def break_down_prompt(prompt: str) -> PromptBreakdown:
    """Return a deterministic nuclear prompt breakdown for any user prompt."""
    cleaned_prompt = _clean(prompt)
    units = _split_units(cleaned_prompt)
    return PromptBreakdown(
        user_goal=_goal_from_prompt(cleaned_prompt, units),
        explicit_requirements=_explicit_requirements(cleaned_prompt, units),
        implicit_requirements=_implicit_requirements(cleaned_prompt),
        constraints=_constraints(cleaned_prompt),
        risk_areas=_risk_areas(cleaned_prompt),
        needed_evidence=_needed_evidence(cleaned_prompt),
        success_criteria=_success_criteria(cleaned_prompt),
        allowed_tools=_allowed_tools(cleaned_prompt),
        validation_plan=_validation_plan(cleaned_prompt),
        stop_conditions=_stop_conditions(cleaned_prompt),
    )


def _complexity(prompt: str, explicit_complexity: int = 0) -> int:
    if explicit_complexity > 0:
        return max(1, min(explicit_complexity, 5))

    score = 1
    lower = prompt.lower()
    if len(prompt) > 600:
        score += 1
    if _contains_any(prompt, _CODE_TERMS):
        score += 1
    if _contains_any(prompt, _RESEARCH_TERMS):
        score += 1
    if _contains_any(prompt, _RISK_TERMS):
        score += 1
    if any(term in lower for term in ("end to end", "absolute", "top tier", "everything", "always", "sync")):
        score += 1
    return max(1, min(score, 5))


def select_reasoning_protocol(prompt: str, complexity: int = 0) -> ProtocolRecommendation:
    """Select a research-inspired protocol stack using deterministic prompt signals."""
    level = _complexity(prompt, complexity)
    lower = prompt.lower()
    is_code = _contains_any(prompt, _CODE_TERMS)
    is_research = _contains_any(prompt, _RESEARCH_TERMS)
    is_debug = any(term in lower for term in ("debug", "bug", "fix", "failing", "error", "crash", "traceback"))
    is_tooling = any(term in lower for term in ("mcp", "tool", "install", "configure", "api", "server"))

    supporting: list[ReasoningProtocol] = []
    rationale: list[str] = []

    if level <= 1 and not (is_code or is_research or is_tooling):
        selected: ReasoningProtocol = "direct"
        rationale.append("Prompt has low risk and low ambiguity; extra process would reduce ROI.")
    elif is_debug:
        selected = "Self-Debugging"
        supporting.extend(["ReAct", "Reflexion"])
        rationale.append(
            "Debugging benefits from reproduce → inspect → patch → validate loops with reflection after failure."
        )
    elif is_research and level >= 3:
        selected = "Evidence-Grounded Research"
        supporting.extend(["Self-Consistency", "Tree-of-Thoughts"])
        rationale.append(
            "Research/benchmark claims need evidence mapping, contradiction checks, and alternative hypotheses."
        )
    elif level >= 4:
        selected = "Tree-of-Thoughts"
        supporting.extend(["ReAct", "Reflexion", "Self-Consistency"])
        rationale.append("High-complexity work should branch across approaches before committing to one path.")
    elif is_tooling or is_code:
        selected = "ReAct"
        supporting.extend(["Self-Debugging", "Reflexion"])
        rationale.append("Tooling/code work needs interleaved reasoning, action, observation, and validation.")
    else:
        selected = "direct"
        supporting.append("Self-Consistency")
        rationale.append("A concise direct answer is enough, with a lightweight consistency check.")

    if is_code:
        rationale.append("Executable validation is available and should dominate confidence.")
    if _contains_any(prompt, _RISK_TERMS):
        rationale.append("Risk terms require explicit guardrails and fail-closed behavior where possible.")

    steps = _execution_steps(selected, tuple(supporting))
    escalation = (
        "Escalate to Tree-of-Thoughts when the first viable plan has unresolved tradeoffs.",
        "Escalate to Evidence-Grounded Research when claims depend on current facts or benchmarks.",
        "Escalate to Self-Debugging when validation fails or observations contradict assumptions.",
        "Stop escalating when added tool/reasoning cost is unlikely to change the outcome.",
    )
    return ProtocolRecommendation(
        selected_protocol=selected,
        supporting_protocols=_dedupe(list(supporting)),
        rationale=tuple(rationale),
        execution_steps=steps,
        escalation_triggers=escalation,
    )


def _execution_steps(selected: ReasoningProtocol, supporting: tuple[ReasoningProtocol, ...]) -> tuple[str, ...]:
    steps_by_protocol: dict[ReasoningProtocol, tuple[str, ...]] = {
        "direct": (
            "Answer the smallest complete version of the request.",
            "Check the answer against explicit requirements before finalizing.",
        ),
        "ReAct": (
            "Reason about the next missing fact or file before each action.",
            "Use the minimum tool call that can resolve that uncertainty.",
            "Update the plan from observations instead of following stale assumptions.",
            "Validate the final state with executable checks where available.",
        ),
        "Tree-of-Thoughts": (
            "Generate 2-3 plausible solution branches before editing or deciding.",
            "Score branches by task success, risk reduction, evidence, and ROI.",
            "Execute the highest-value branch, keeping fallback criteria explicit.",
        ),
        "Reflexion": (
            "After each failed check, record what assumption was wrong.",
            "Revise the plan with the new lesson before retrying.",
        ),
        "Self-Consistency": (
            "Compare independent reasoning paths for agreement on the final answer.",
            "Investigate contradictions before presenting a confident conclusion.",
        ),
        "Self-Debugging": (
            "Reproduce or inspect the failure before patching.",
            "Explain the suspected root cause in concrete state terms.",
            "Patch the root cause and rerun the failing check.",
        ),
        "Evidence-Grounded Research": (
            "Break claims into atomic assertions.",
            "Attach evidence or label each assertion as an assumption.",
            "Check for contradictory evidence and recency gaps.",
            "Calibrate confidence to evidence strength.",
        ),
    }

    ordered_protocols = (selected, *supporting)
    steps: list[str] = []
    for protocol in ordered_protocols:
        steps.extend(steps_by_protocol[protocol])
    return _dedupe(steps, limit=12)


def nuclear_prompt_breakdown(prompt: str) -> dict[str, object]:
    """JSON-compatible prompt breakdown API."""
    return break_down_prompt(prompt).to_dict()


def protocol_recommendation(prompt: str, complexity: int = 0) -> dict[str, object]:
    """JSON-compatible protocol recommendation API."""
    return select_reasoning_protocol(prompt, complexity).to_dict()


def _section(title: str, values: tuple[str, ...]) -> list[str]:
    lines = [f"## {title}"]
    for value in values:
        lines.append(f"- {value}")
    return lines


def nuclear_prompt_markdown(prompt: str) -> str:
    """Render the prompt breakdown as structured Markdown plus JSON."""
    breakdown = break_down_prompt(prompt)
    data = breakdown.to_dict()
    lines = [
        "# Nuclear Prompt Breakdown",
        "",
        f"**User goal:** {breakdown.user_goal}",
        "",
    ]
    lines.extend(_section("Explicit Requirements", breakdown.explicit_requirements))
    lines.append("")
    lines.extend(_section("Implicit Requirements", breakdown.implicit_requirements))
    lines.append("")
    lines.extend(_section("Constraints", breakdown.constraints))
    lines.append("")
    lines.extend(_section("Risk Areas", breakdown.risk_areas))
    lines.append("")
    lines.extend(_section("Needed Evidence", breakdown.needed_evidence))
    lines.append("")
    lines.extend(_section("Success Criteria", breakdown.success_criteria))
    lines.append("")
    lines.extend(_section("Allowed Tools", breakdown.allowed_tools))
    lines.append("")
    lines.extend(_section("Validation Plan", breakdown.validation_plan))
    lines.append("")
    lines.extend(_section("Stop Conditions", breakdown.stop_conditions))
    lines.extend(["", "## JSON", "```json", json.dumps(data, indent=2, sort_keys=True), "```"])
    return "\n".join(lines)


def protocol_recommendation_markdown(prompt: str, complexity: int = 0) -> str:
    """Render the selected reasoning protocol stack as Markdown plus JSON."""
    recommendation = select_reasoning_protocol(prompt, complexity)
    data = recommendation.to_dict()
    lines = [
        "# Reasoning Protocol Recommendation",
        "",
        f"**Selected protocol:** `{recommendation.selected_protocol}`",
        f"**Supporting protocols:** {', '.join(f'`{p}`' for p in recommendation.supporting_protocols) or 'none'}",
        "",
    ]
    lines.extend(_section("Rationale", recommendation.rationale))
    lines.append("")
    lines.extend(_section("Execution Steps", recommendation.execution_steps))
    lines.append("")
    lines.extend(_section("Escalation / Stop Triggers", recommendation.escalation_triggers))
    lines.extend(["", "## JSON", "```json", json.dumps(data, indent=2, sort_keys=True), "```"])
    return "\n".join(lines)
