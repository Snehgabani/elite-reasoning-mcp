"""Deterministic experiment-tree planner for complex agent tasks.

This is a lightweight Tree-of-Thoughts / Reflexion inspired scaffold. It gives
weaker models explicit branches, hypotheses, expected observations, and stopping
criteria without sampling multiple LLM completions.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from core.reasoning.nuclear_prompt import break_down_prompt, select_reasoning_protocol


@dataclass(frozen=True)
class ExperimentBranch:
    """One candidate branch in a deterministic reasoning experiment tree."""

    name: str
    hypothesis: str
    candidate_approach: str
    validation_methods: tuple[str, ...]
    risks: tuple[str, ...]
    fallback_paths: tuple[str, ...]
    expected_observations: tuple[str, ...]
    stopping_criteria: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentTree:
    """Structured branch plan with global reflection hooks."""

    root_goal: str
    selected_protocol: str
    branches: tuple[ExperimentBranch, ...]
    global_stopping_criteria: tuple[str, ...]
    reflection_questions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def _clamp_branches(max_branches: int) -> int:
    return min(max(1, max_branches), 5)


def _base_branch_templates(prompt: str) -> list[dict[str, object]]:
    is_code = _contains_any(prompt, ("code", "repo", "test", "implement", "fix", "debug", "mcp", "api", "tool"))
    is_research = _contains_any(prompt, ("research", "paper", "benchmark", "evidence", "quality", "eval", "roi"))
    is_install = _contains_any(prompt, ("install", "configure", "restart", "zed", "mcp", "server"))
    templates: list[dict[str, object]] = []

    if is_code:
        templates.append(
            {
                "name": "Surgical implementation branch",
                "hypothesis": "A minimal code change that follows existing patterns will deliver the highest ROI with the least regression risk.",
                "candidate_approach": "Inspect local patterns, add the smallest cohesive module/tool wrapper changes, then validate with targeted tests.",
                "validation_methods": (
                    "Run unit tests closest to the changed modules.",
                    "Run configured lint/static checks for touched packages.",
                    "Smoke-test imports or installed entry points when exposure changes.",
                ),
                "risks": (
                    "The local source may pass tests while installed runtime remains stale.",
                    "The new tool surface may not be registered in the MCP server.",
                ),
                "fallback_paths": (
                    "If registration fails, inspect the MCP registration function and add a thin wrapper there.",
                    "If tests reveal coupling, reduce scope and isolate deterministic helpers from MCP wrappers.",
                ),
                "expected_observations": (
                    "Diff is limited to focused modules/tests.",
                    "Tests exercise both data structures and rendered tool output.",
                ),
                "stopping_criteria": (
                    "Targeted tests and lint pass.",
                    "Installed/runtime smoke import confirms the new code is packaged.",
                ),
            }
        )

    if is_research:
        templates.append(
            {
                "name": "Evidence-first benchmark branch",
                "hypothesis": "Quality improves most when claims are tied to measurable benchmark dimensions and contradiction checks.",
                "candidate_approach": "Map the request to outcome metrics, benchmark families, evidence needs, and confidence/calibration hooks before recommending features.",
                "validation_methods": (
                    "Check every major claim has a benchmark/source or is labeled as an assumption.",
                    "Score the output against task success, evidence quality, calibration, robustness, and ROI.",
                ),
                "risks": (
                    "Benchmark names can become decorative instead of changing decisions.",
                    "Claims can overstate current research if no recency check is performed.",
                ),
                "fallback_paths": (
                    "If evidence is stale or unavailable, lower confidence and propose a reproducible eval instead of a claim.",
                    "If benchmark alignment is weak, switch to local fixture-based evaluation first.",
                ),
                "expected_observations": (
                    "The plan mentions measurable outcomes rather than vague intelligence gains.",
                    "Uncertainty is explicit where evidence is indirect.",
                ),
                "stopping_criteria": (
                    "Each recommendation maps to at least one scorecard dimension.",
                    "No unsupported state-of-the-art claim remains unqualified.",
                ),
            }
        )

    if is_install:
        templates.append(
            {
                "name": "Capability and sync branch",
                "hypothesis": "End-to-end reliability depends on client capability verification and sync-safe defaults, not just local code edits.",
                "candidate_approach": "Verify the active IDE exposes the MCP tools, keep operations idempotent, and smoke-test after reinstall/restart boundaries.",
                "validation_methods": (
                    "Run capability discovery for the active client.",
                    "Check packaging/install commands complete successfully.",
                    "Verify new tool imports from the installed environment.",
                ),
                "risks": (
                    "Zed may not expose legacy skills or newly installed tools until restart.",
                    "Open sync/test modes can leak into production defaults.",
                ),
                "fallback_paths": (
                    "If the client cannot see the tool, inspect settings and require a restart before claiming success.",
                    "If sync/auth state is ambiguous, fail closed and document the required key or opt-in flag.",
                ),
                "expected_observations": (
                    "Capability report lists the intended MCP server as recommendable.",
                    "New tools are available after package reinstall and client restart.",
                ),
                "stopping_criteria": (
                    "Installed package import/smoke check passes.",
                    "Any required restart or setting change is stated explicitly.",
                ),
            }
        )

    templates.append(
        {
            "name": "ROI control branch",
            "hypothesis": "The best answer maximizes outcome improvement per tool call and avoids process theater.",
            "candidate_approach": "Use the simplest sufficient workflow, escalate only when uncertainty or risk remains, and record validation evidence.",
            "validation_methods": (
                "Compare planned effort against expected quality improvement.",
                "Check whether another branch would materially change the result.",
            ),
            "risks": (
                "Extra analysis can delay delivery without improving correctness.",
                "Too little analysis can miss implicit requirements or hidden dependencies.",
            ),
            "fallback_paths": (
                "Escalate to a deeper branch if validation fails or requirements conflict.",
                "De-escalate to a direct answer if the prompt is low-risk and clear.",
            ),
            "expected_observations": (
                "Tool calls are tied to unresolved uncertainties.",
                "The final answer names what was validated and what remains unknown.",
            ),
            "stopping_criteria": (
                "No unresolved high-impact uncertainty remains.",
                "Additional work is unlikely to change the final recommendation or implementation.",
            ),
        }
    )
    return templates


def build_experiment_tree(prompt: str, max_branches: int = 3) -> dict[str, object]:
    """Return a JSON-compatible experiment tree for a prompt."""
    return _build_tree(prompt, max_branches).to_dict()


def _build_tree(prompt: str, max_branches: int = 3) -> ExperimentTree:
    breakdown = break_down_prompt(prompt)
    protocol = select_reasoning_protocol(prompt)
    templates = _base_branch_templates(prompt)
    branch_count = _clamp_branches(max_branches)
    branches = tuple(ExperimentBranch(**template) for template in templates[:branch_count])
    return ExperimentTree(
        root_goal=breakdown.user_goal,
        selected_protocol=protocol.selected_protocol,
        branches=branches,
        global_stopping_criteria=breakdown.stop_conditions,
        reflection_questions=(
            "Which assumption would invalidate the chosen branch?",
            "What observation would prove this branch is failing?",
            "What cheaper validation can reduce the largest remaining risk?",
            "Did the workflow improve outcome quality or only add process?",
        ),
    )


def _bullet_section(title: str, values: tuple[str, ...]) -> list[str]:
    lines = [f"### {title}"]
    lines.extend(f"- {value}" for value in values)
    return lines


def experiment_tree_markdown(prompt: str, max_branches: int = 3) -> str:
    """Render the deterministic experiment tree as Markdown plus JSON."""
    tree = _build_tree(prompt, max_branches)
    data = tree.to_dict()
    lines = [
        "# Elite Experiment Tree",
        "",
        f"**Root goal:** {tree.root_goal}",
        f"**Selected protocol:** `{tree.selected_protocol}`",
        f"**Branches:** {len(tree.branches)}",
        "",
    ]
    for index, branch in enumerate(tree.branches, start=1):
        lines.extend(
            [
                f"## Branch {index}: {branch.name}",
                f"**Hypothesis:** {branch.hypothesis}",
                f"**Candidate approach:** {branch.candidate_approach}",
                "",
            ]
        )
        lines.extend(_bullet_section("Validation Methods", branch.validation_methods))
        lines.append("")
        lines.extend(_bullet_section("Risks", branch.risks))
        lines.append("")
        lines.extend(_bullet_section("Fallback Paths", branch.fallback_paths))
        lines.append("")
        lines.extend(_bullet_section("Expected Observations", branch.expected_observations))
        lines.append("")
        lines.extend(_bullet_section("Stopping Criteria", branch.stopping_criteria))
        lines.append("")

    lines.extend(_bullet_section("Global Stopping Criteria", tree.global_stopping_criteria))
    lines.append("")
    lines.extend(_bullet_section("Reflection Questions", tree.reflection_questions))
    lines.extend(["", "## JSON", "```json", json.dumps(data, indent=2, sort_keys=True), "```"])
    return "\n".join(lines)
