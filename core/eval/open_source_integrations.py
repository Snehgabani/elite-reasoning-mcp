"""Optional open-source integration manifest for Elite Reasoning MCP.

The core MCP stays lightweight. This module recommends adoptable frameworks and
provider options as optional next steps with install/config snippets instead of
adding hard dependencies.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class IntegrationRecommendation:
    """One optional open-source integration recommendation."""

    name: str
    category: str
    best_for: tuple[str, ...]
    why_it_matters: str
    adoption_mode: str
    install_commands: tuple[str, ...]
    config_snippet: str
    guardrails: tuple[str, ...]
    maturity_notes: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


INTEGRATIONS: tuple[IntegrationRecommendation, ...] = (
    IntegrationRecommendation(
        name="GEPA / DSPy",
        category="prompt_optimization",
        best_for=("reflective prompt evolution", "small-model uplift", "Pareto prompt search", "few-eval optimization"),
        why_it_matters=(
            "GEPA-style reflective prompt evolution can optimize prompts against task feedback, which is useful when "
            "weaker/open-source models need explicit scaffolds tuned to local evals."
        ),
        adoption_mode="Optional adapter/exporter; do not make core MCP depend on DSPy/GEPA.",
        install_commands=(
            "uv add --optional eval dspy-ai",
            "uv run python -m pip install gepa dspy-ai",
        ),
        config_snippet=(
            "# Future adapter idea\n"
            "# 1. Export Elite eval fixtures as DSPy examples.\n"
            "# 2. Optimize nuclear prompt templates against pass/fail feedback.\n"
            "# 3. Keep the winning prompt as a versioned artifact, not runtime magic."
        ),
        guardrails=(
            "Use held-out eval fixtures to avoid overfitting prompts.",
            "Track task_success and regression_prevention deltas, not just optimizer score.",
            "Keep optimized prompts reviewable and version controlled.",
        ),
        maturity_notes="Promising for prompt/program optimization; keep optional because dependency surface and APIs may change.",
    ),
    IntegrationRecommendation(
        name="Promptfoo",
        category="eval_red_team_ci",
        best_for=("prompt regression tests", "red teaming", "prompt injection", "CI gates", "provider comparison"),
        why_it_matters=(
            "Promptfoo is a practical open-source path for CI-friendly evals, red-team probes, and provider comparisons "
            "across hosted and local models."
        ),
        adoption_mode="Generate promptfooconfig.yaml from Elite fixtures; run outside core MCP.",
        install_commands=(
            "npm install -g promptfoo",
            "promptfoo init",
            "promptfoo eval",
        ),
        config_snippet=(
            "# promptfooconfig.yaml sketch\n"
            "prompts:\n"
            "  - file://prompts/nuclear_prompt.md\n"
            "providers:\n"
            "  - ollama:chat:llama3.1\n"
            "tests:\n"
            "  - vars:\n"
            "      task: 'Fix a failing repo test with validation'\n"
            "    assert:\n"
            "      - type: contains-any\n"
            "        value: ['pytest', 'validation', 'root cause']"
        ),
        guardrails=(
            "Run red-team suites separately from normal smoke tests to keep latency predictable.",
            "Treat provider API keys as environment variables only.",
            "Fail CI on regressions in high-risk prompts, warn on exploratory evals.",
        ),
        maturity_notes="Strong fit for practical prompt regression and security testing with low coupling to Python core.",
    ),
    IntegrationRecommendation(
        name="DeepEval",
        category="pytest_native_llm_eval",
        best_for=("pytest workflows", "agent task completion", "hallucination metrics", "G-Eval style scoring"),
        why_it_matters=(
            "DeepEval can make LLM evals feel like normal tests, which fits this repo's pytest validation flow and future "
            "MCP-on/MCP-off comparisons."
        ),
        adoption_mode="Optional pytest eval package; keep deterministic smoke suite as the always-on baseline.",
        install_commands=(
            "uv add --optional eval deepeval",
            "uv run deepeval test run tests/evals",
        ),
        config_snippet=(
            "# tests/evals/test_elite_reasoning.py sketch\n"
            "# from deepeval import assert_test\n"
            "# Compare MCP-on vs MCP-off outputs on task_success, hallucination, and tool correctness."
        ),
        guardrails=(
            "Do not block local unit tests on external judge availability.",
            "Pin evaluator prompts and model versions for reproducibility.",
            "Use deterministic checks for security-critical assertions before judge scores.",
        ),
        maturity_notes="Good optional bridge for teams already comfortable with pytest and LLM-as-judge evals.",
    ),
    IntegrationRecommendation(
        name="Inspect AI",
        category="rigorous_model_agent_eval",
        best_for=("security-grade evals", "agent trajectories", "scorers", "eval logs", "model API abstraction"),
        why_it_matters=(
            "Inspect AI is designed for rigorous model/agent evaluations with tasks, solvers, scorers, and reproducible logs; "
            "it is suitable for higher-stakes benchmark campaigns."
        ),
        adoption_mode="Optional research/eval harness for scheduled benchmark runs, not per-prompt runtime dependency.",
        install_commands=(
            "uv add --optional eval inspect-ai",
            "uv run inspect eval evals/elite_reasoning.py --model openai/gpt-4o-mini",
        ),
        config_snippet=(
            "# evals/elite_reasoning.py sketch\n"
            "# Define tasks from Elite smoke fixtures, solvers for MCP-on/off, and scorers for outcome dimensions."
        ),
        guardrails=(
            "Use for scheduled eval campaigns because it is heavier than local smoke checks.",
            "Keep eval datasets versioned and separate from prompt optimization training data.",
            "Record model/provider versions with every report.",
        ),
        maturity_notes="Best for rigorous eval programs; probably too heavy for default MCP runtime.",
    ),
    IntegrationRecommendation(
        name="Ollama",
        category="local_model_provider",
        best_for=("local open-source LLMs", "private smoke tests", "offline provider comparison"),
        why_it_matters=(
            "Ollama is a simple local provider target for testing whether the MCP scaffolds improve weaker/open-source models "
            "without sending prompts to hosted APIs."
        ),
        adoption_mode="Provider option for eval frameworks and local experiments.",
        install_commands=(
            "brew install ollama",
            "ollama pull llama3.1",
            "ollama serve",
        ),
        config_snippet=(
            "# Provider target examples\n"
            "# promptfoo: ollama:chat:llama3.1\n"
            "# OpenAI-compatible base_url: http://localhost:11434/v1"
        ),
        guardrails=(
            "Benchmark the exact local model/quantization used by the user.",
            "Do not assume hosted-model quality; rely on eval deltas.",
            "Keep private data local and document resource limits.",
        ),
        maturity_notes="Very practical local provider; performance depends heavily on model and hardware.",
    ),
    IntegrationRecommendation(
        name="llama.cpp",
        category="local_model_runtime",
        best_for=("CPU/GPU local inference", "GGUF models", "low-level reproducible runs"),
        why_it_matters=(
            "llama.cpp gives reproducible local inference for GGUF models and can expose OpenAI-compatible endpoints for eval tools."
        ),
        adoption_mode="Provider/runtime option for advanced local benchmarking.",
        install_commands=(
            "brew install llama.cpp",
            "llama-server -m /path/to/model.gguf --port 8080",
        ),
        config_snippet=(
            "# OpenAI-compatible local endpoint\nbase_url: http://localhost:8080/v1\nmodel: local-gguf-model"
        ),
        guardrails=(
            "Record model hash, quantization, context length, and sampling params.",
            "Use deterministic seeds/temperature where supported for comparisons.",
            "Watch for context truncation on long nuclear breakdown prompts.",
        ),
        maturity_notes="Excellent for reproducible local evals; requires more setup than Ollama.",
    ),
    IntegrationRecommendation(
        name="vLLM",
        category="high_throughput_model_provider",
        best_for=("GPU serving", "batch evals", "OpenAI-compatible server", "throughput benchmarks"),
        why_it_matters=(
            "vLLM is useful when running larger eval suites against open-source models because throughput and batching matter."
        ),
        adoption_mode="Provider/runtime for larger benchmark campaigns, not a default local requirement.",
        install_commands=(
            "uv pip install vllm",
            "python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-3.1-8B-Instruct",
        ),
        config_snippet=(
            "# OpenAI-compatible eval provider\n"
            "base_url: http://localhost:8000/v1\n"
            "model: meta-llama/Llama-3.1-8B-Instruct"
        ),
        guardrails=(
            "Use only on compatible GPU environments.",
            "Track latency/cost ROI and throughput separately from answer quality.",
            "Pin model revision and sampling parameters for repeatability.",
        ),
        maturity_notes="Strong for throughput; too environment-specific to ship as a required MCP dependency.",
    ),
)


def _score_match(integration: IntegrationRecommendation, use_case: str) -> int:
    if not use_case:
        return 1
    query_terms = {term for term in use_case.lower().replace("/", " ").replace("-", " ").split() if len(term) > 2}
    haystack = " ".join(
        (
            integration.name,
            integration.category,
            integration.why_it_matters,
            " ".join(integration.best_for),
            integration.adoption_mode,
        )
    ).lower()
    return sum(1 for term in query_terms if term in haystack)


def recommend_open_source_integrations(use_case: str = "") -> dict[str, object]:
    """Return optional open-source integration recommendations as JSON-compatible data."""
    scored = [(integration, _score_match(integration, use_case)) for integration in INTEGRATIONS]
    selected = [integration for integration, score in scored if score > 0]
    if use_case and not selected:
        selected = list(INTEGRATIONS)
    return {
        "use_case": use_case,
        "dependency_policy": "Core MCP remains dependency-light; integrations are optional adapters/exporters/providers.",
        "recommendations": [integration.to_dict() for integration in selected],
        "adoption_sequence": (
            "Start with the built-in deterministic smoke suite.",
            "Export fixtures to Promptfoo or DeepEval for CI/provider comparison.",
            "Use GEPA/DSPy only after a stable held-out eval set exists.",
            "Use Inspect AI/vLLM for scheduled research-grade benchmark campaigns.",
            "Use Ollama or llama.cpp for private local-model uplift experiments.",
        ),
    }


def integrations_markdown(use_case: str = "") -> str:
    """Render optional integration recommendations as Markdown plus JSON."""
    data = recommend_open_source_integrations(use_case)
    recommendations = data["recommendations"]
    lines = [
        "# Optional Open-Source Integration Recommendations",
        "",
        f"**Use case filter:** {use_case or 'all'}",
        f"**Dependency policy:** {data['dependency_policy']}",
        "",
        "## Recommended Adoption Sequence",
    ]
    lines.extend(f"- {step}" for step in data["adoption_sequence"])
    lines.extend(["", "## Integrations"])
    for rec in recommendations:
        lines.extend(
            [
                f"### {rec['name']}",
                f"- Category: `{rec['category']}`",
                f"- Best for: {', '.join(rec['best_for'])}",
                f"- Why it matters: {rec['why_it_matters']}",
                f"- Adoption mode: {rec['adoption_mode']}",
                "- Install commands:",
            ]
        )
        lines.extend(f"  - `{command}`" for command in rec["install_commands"])
        lines.append("- Guardrails:")
        lines.extend(f"  - {guardrail}" for guardrail in rec["guardrails"])
        lines.extend(["- Config snippet:", "```text", rec["config_snippet"], "```", ""])
    lines.extend(["## JSON", "```json", json.dumps(data, indent=2, sort_keys=True), "```"])
    return "\n".join(lines)
