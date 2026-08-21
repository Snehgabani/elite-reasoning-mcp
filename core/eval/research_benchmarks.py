"""Research-backed benchmark catalog and ROI policy for reasoning agents.

This module does not run external benchmarks directly. It gives the MCP a
research-grounded evaluation plan so teams can measure whether reasoning tools
actually improve outcomes instead of merely adding ceremony.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

TaskClass = Literal[
    "coding_agent",
    "code_generation",
    "tool_use",
    "interactive_agent",
    "research_grounding",
    "calibration",
    "holistic_quality",
]


@dataclass(frozen=True)
class BenchmarkSource:
    """A benchmark family with the metric it contributes to Elite evals."""

    name: str
    task_class: TaskClass
    use_for: str
    primary_metrics: tuple[str, ...]
    citation: str
    url: str
    notes: str = ""


@dataclass(frozen=True)
class EvalDimension:
    """One dimension in the Elite quality scorecard."""

    name: str
    weight: float
    metric: str
    rationale: str
    benchmark_sources: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ToolBudgetPolicy:
    """Recommended reasoning/tool budget for a task risk tier."""

    tier: str
    max_tool_calls: int
    max_latency_ms: int
    required_checks: tuple[str, ...]
    escalation_condition: str


BENCHMARK_CATALOG: tuple[BenchmarkSource, ...] = (
    BenchmarkSource(
        name="SWE-bench Verified",
        task_class="coding_agent",
        use_for="Real-world GitHub issue resolution with executable fail-to-pass tests.",
        primary_metrics=("percent_resolved", "fail_to_pass_tests", "patch_correctness"),
        citation="Jimenez et al., SWE-bench: Can Language Models Resolve Real-world GitHub Issues?, ICLR 2024; Verified subset introduced with human filtering.",
        url="https://www.swebench.com/",
        notes="Use the Verified/Lite tiers for affordable regression checks before attempting full benchmark runs.",
    ),
    BenchmarkSource(
        name="HumanEval",
        task_class="code_generation",
        use_for="Function-level code synthesis sanity checks.",
        primary_metrics=("pass@1", "unit_test_pass_rate"),
        citation="Chen et al., Evaluating Large Language Models Trained on Code, 2021.",
        url="https://github.com/openai/human-eval",
        notes="Good smoke test, but too narrow for agentic repo work; pair with SWE-bench style tasks.",
    ),
    BenchmarkSource(
        name="MBPP",
        task_class="code_generation",
        use_for="Introductory Python programming tasks with test cases.",
        primary_metrics=("pass@1", "unit_test_pass_rate"),
        citation="Austin et al., Program Synthesis with Large Language Models, 2021.",
        url="https://github.com/google-research/google-research/tree/master/mbpp",
    ),
    BenchmarkSource(
        name="API-Bank",
        task_class="tool_use",
        use_for="Tool retrieval, tool-call planning, and API execution dialogues.",
        primary_metrics=("tool_selection_accuracy", "api_call_success", "plan_success"),
        citation="Li et al., API-Bank: A Comprehensive Benchmark for Tool-Augmented LLMs, EMNLP 2023.",
        url="https://arxiv.org/abs/2304.08244",
    ),
    BenchmarkSource(
        name="ToolBench",
        task_class="tool_use",
        use_for="Multi-step real-tool use and tool-routing stress tests.",
        primary_metrics=("tool_success_rate", "multi_step_completion", "unnecessary_tool_rate"),
        citation="Qin et al., ToolBench: Towards Advancing Large Language Models with Tools, 2023.",
        url="https://arxiv.org/abs/2307.16789",
    ),
    BenchmarkSource(
        name="AgentBench",
        task_class="interactive_agent",
        use_for="Long-horizon agent decision-making across interactive environments.",
        primary_metrics=("task_success", "turn_efficiency", "instruction_following"),
        citation="Liu et al., AgentBench: Evaluating LLMs as Agents, ICLR 2024.",
        url="https://github.com/THUDM/AgentBench",
    ),
    BenchmarkSource(
        name="HELM-style multi-metric evaluation",
        task_class="holistic_quality",
        use_for="Balanced scorecards beyond accuracy: calibration, robustness, fairness, toxicity, efficiency.",
        primary_metrics=("accuracy", "calibration", "robustness", "efficiency"),
        citation="Liang/Bommasani et al., Holistic Evaluation of Language Models, 2022/2023.",
        url="https://crfm.stanford.edu/helm/latest/",
        notes="Elite MCP should report trade-offs, not a single vanity score.",
    ),
    BenchmarkSource(
        name="FEVER / evidence verification pattern",
        task_class="research_grounding",
        use_for="Claim-evidence-support/refute/insufficient-evidence discipline.",
        primary_metrics=("claim_support_precision", "contradiction_detection", "citation_coverage"),
        citation="Thorne et al., FEVER: a Large-scale Dataset for Fact Extraction and VERification, NAACL 2018.",
        url="https://fever.ai/",
    ),
    BenchmarkSource(
        name="TruthfulQA",
        task_class="research_grounding",
        use_for="Truthfulness and hallucination resistance on adversarial questions.",
        primary_metrics=("truthfulness", "informativeness", "hallucination_rate"),
        citation="Lin, Hilton, Evans, TruthfulQA: Measuring How Models Mimic Human Falsehoods, ACL 2022.",
        url="https://github.com/sylinrl/TruthfulQA",
    ),
    BenchmarkSource(
        name="Brier score calibration",
        task_class="calibration",
        use_for="Measure whether confidence estimates match actual outcomes.",
        primary_metrics=("brier_score", "expected_calibration_error", "overconfidence_rate"),
        citation="Brier, Verification of Forecasts Expressed in Terms of Probability, Monthly Weather Review, 1950.",
        url="https://en.wikipedia.org/wiki/Brier_score",
        notes="Already partially supported by Elite calibration tools; add mandatory outcome resolution cadence.",
    ),
)


ELITE_SCORECARD: tuple[EvalDimension, ...] = (
    EvalDimension(
        name="task_success",
        weight=0.30,
        metric="Executable validation or accepted user outcome",
        rationale="The final answer must solve the task; this dominates all process metrics.",
        benchmark_sources=("SWE-bench Verified", "AgentBench"),
    ),
    EvalDimension(
        name="regression_prevention",
        weight=0.18,
        metric="Fail-to-pass plus pass-to-pass preservation / repeated mistake reduction",
        rationale="A reasoning MCP should reduce repeated failures and avoid breaking working behavior.",
        benchmark_sources=("SWE-bench Verified",),
    ),
    EvalDimension(
        name="tool_efficiency",
        weight=0.14,
        metric="Useful tool calls divided by total tool calls; unnecessary tool rate",
        rationale="Elite reasoning uses the right tools, not the most tools.",
        benchmark_sources=("API-Bank", "ToolBench"),
    ),
    EvalDimension(
        name="evidence_quality",
        weight=0.14,
        metric="Citation coverage, source quality, contradiction handling, recency",
        rationale="Research-grade answers require traceable evidence and explicit uncertainty.",
        benchmark_sources=("FEVER / evidence verification pattern", "TruthfulQA"),
    ),
    EvalDimension(
        name="calibration",
        weight=0.10,
        metric="Brier score / overconfidence rate for predictions and recommendations",
        rationale="The system should know when it might be wrong.",
        benchmark_sources=("Brier score calibration", "HELM-style multi-metric evaluation"),
    ),
    EvalDimension(
        name="latency_cost_roi",
        weight=0.08,
        metric="Quality gain per second and per tool call",
        rationale="Quality improvements must justify added friction.",
        benchmark_sources=("HELM-style multi-metric evaluation",),
    ),
    EvalDimension(
        name="robustness",
        weight=0.06,
        metric="Performance under missing tools, stale docs, partial failures, huge input",
        rationale="Agent systems fail at the seams; robustness must be measured directly.",
        benchmark_sources=("AgentBench", "HELM-style multi-metric evaluation"),
    ),
)


TOOL_BUDGET_POLICIES: tuple[ToolBudgetPolicy, ...] = (
    ToolBudgetPolicy(
        tier="trivial",
        max_tool_calls=0,
        max_latency_ms=500,
        required_checks=(),
        escalation_condition="User asks for implementation, debugging, security, architecture, or research evidence.",
    ),
    ToolBudgetPolicy(
        tier="standard",
        max_tool_calls=2,
        max_latency_ms=4000,
        required_checks=("elite_verify:constraints",),
        escalation_condition="Uncertainty > 0.30, code changes touch more than one file, or validation is unavailable.",
    ),
    ToolBudgetPolicy(
        tier="high_risk",
        max_tool_calls=4,
        max_latency_ms=8000,
        required_checks=("elite_verify:constraints", "elite_memory:search"),
        escalation_condition="Auth, payments, data deletion, migrations, production deploys, or irreversible state changes.",
    ),
    ToolBudgetPolicy(
        tier="research_grade",
        max_tool_calls=3,
        max_latency_ms=12000,
        required_checks=("elite_verify:evidence", "elite_verify:grounding"),
        escalation_condition="Claims require current data, citations, scientific/medical/security accuracy, or benchmark comparisons.",
    ),
)


def benchmark_catalog_markdown(task_class: str = "") -> str:
    """Render benchmark sources filtered by task class."""
    sources = [src for src in BENCHMARK_CATALOG if not task_class or src.task_class == task_class]
    lines = ["# Research-Backed Benchmark Catalog", ""]
    if task_class:
        lines.append(f"Filtered by task class: `{task_class}`")
        lines.append("")
    lines.append("| Benchmark | Class | Use | Primary Metrics | Source |")
    lines.append("|---|---|---|---|---|")
    for src in sources:
        lines.append(
            f"| {src.name} | `{src.task_class}` | {src.use_for} | "
            f"{', '.join(src.primary_metrics)} | [{src.citation}]({src.url}) |"
        )
    return "\n".join(lines)


def scorecard_markdown() -> str:
    """Render the Elite outcome scorecard."""
    lines = ["# Elite Outcome Scorecard", ""]
    lines.append("| Dimension | Weight | Metric | Rationale | Benchmarks |")
    lines.append("|---|---:|---|---|---|")
    for dim in ELITE_SCORECARD:
        lines.append(
            f"| `{dim.name}` | {dim.weight:.2f} | {dim.metric} | {dim.rationale} | {', '.join(dim.benchmark_sources)} |"
        )
    lines.append("")
    lines.append(f"**Total weight:** {sum(dim.weight for dim in ELITE_SCORECARD):.2f}")
    return "\n".join(lines)


def recommend_budget_tier(prompt: str, complexity: int = 0) -> ToolBudgetPolicy:
    """Recommend a reasoning/tool budget tier from prompt risk signals."""
    p = prompt.lower()
    high_risk = [
        "auth",
        "authentication",
        "payment",
        "billing",
        "delete",
        "destructive",
        "migration",
        "production",
        "security",
        "secret",
        "credential",
        "compliance",
    ]
    research = [
        "research",
        "paper",
        "citation",
        "benchmark",
        "evidence",
        "medical",
        "scientific",
        "clinical",
        "legal",
        "compare models",
        "state of the art",
    ]
    standard = ["build", "implement", "debug", "fix", "refactor", "test", "audit", "deploy"]

    if complexity >= 5 or any(term in p for term in research):
        return next(policy for policy in TOOL_BUDGET_POLICIES if policy.tier == "research_grade")
    if complexity >= 4 or any(term in p for term in high_risk):
        return next(policy for policy in TOOL_BUDGET_POLICIES if policy.tier == "high_risk")
    if complexity >= 2 or any(term in p for term in standard):
        return next(policy for policy in TOOL_BUDGET_POLICIES if policy.tier == "standard")
    return next(policy for policy in TOOL_BUDGET_POLICIES if policy.tier == "trivial")


def budget_policy_markdown(prompt: str = "", complexity: int = 0) -> str:
    """Render the tool budget recommendation and all available policies."""
    selected = recommend_budget_tier(prompt, complexity)
    lines = [
        "# Adaptive ROI / Tool Budget Policy",
        "",
        f"**Recommended tier:** `{selected.tier}`",
        f"**Max tool calls:** {selected.max_tool_calls}",
        f"**Max latency:** {selected.max_latency_ms} ms",
        f"**Required checks:** {', '.join(selected.required_checks) if selected.required_checks else 'none'}",
        f"**Escalate when:** {selected.escalation_condition}",
        "",
        "## Policy Table",
        "| Tier | Max Calls | Max Latency | Required Checks | Escalation |",
        "|---|---:|---:|---|---|",
    ]
    for policy in TOOL_BUDGET_POLICIES:
        lines.append(
            f"| `{policy.tier}` | {policy.max_tool_calls} | {policy.max_latency_ms} ms | "
            f"{', '.join(policy.required_checks) if policy.required_checks else 'none'} | "
            f"{policy.escalation_condition} |"
        )
    return "\n".join(lines)
