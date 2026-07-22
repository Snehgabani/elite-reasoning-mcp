# Elite Evaluation Model

Elite Reasoning MCP should not be judged by how many tools it calls. It should be judged by whether it improves measurable outcomes.

## Core principle

```text
More reasoning process is only valuable when it improves correctness, evidence quality, decision quality, or ROI.
```

## Research-backed benchmark families

| Benchmark family | Use inside Elite Reasoning MCP |
|---|---|
| SWE-bench / SWE-bench Verified | Real-world coding-agent issue resolution using executable fail-to-pass tests. |
| HumanEval / MBPP | Fast function-level code-generation smoke tests. |
| API-Bank / ToolBench | Tool retrieval, API-call planning, multi-step tool-use accuracy, and unnecessary tool-call rate. |
| AgentBench | Long-horizon interactive agent decision-making and instruction following. |
| HELM-style evaluation | Multi-metric reporting across accuracy, calibration, robustness, fairness/safety, toxicity, and efficiency. |
| FEVER-style evidence verification | Claim-support/refute/insufficient-evidence discipline for research answers. |
| TruthfulQA | Truthfulness and hallucination-resistance checks. |
| Brier score | Calibration quality for confidence estimates and predictions. |

## Elite outcome scorecard

The legacy compatibility profile exposes `elite_outcome_scorecard()` with this weighted model. The default core profile applies the same discipline through `elite_prepare` validation gates and `elite_verify`.

1. `task_success` — did the answer or code actually solve the task?
2. `regression_prevention` — did it avoid breaking existing behavior and reduce repeated mistakes?
3. `tool_efficiency` — did it use the right tools with minimal waste?
4. `evidence_quality` — are claims cited, current, credible, and contradiction-aware?
5. `calibration` — does confidence match outcomes?
6. `latency_cost_roi` — did the quality gain justify the time/tool overhead?
7. `robustness` — does it survive missing tools, huge inputs, stale docs, and partial failures?

## Tool budget tiers

The legacy compatibility profile exposes `roi_tool_budget(prompt, complexity)` to prevent tool theater. The default core profile assigns the same budget tier when `elite_prepare` creates a workflow run.

| Tier | Intended use |
|---|---|
| `trivial` | No heavy reasoning; answer directly. |
| `standard` | Lightweight orchestration and focused validation. |
| `high_risk` | Security/auth/payment/data/destructive/production work. Requires anti-pattern and confidence checks. |
| `research_grade` | Claims requiring citations, benchmark comparisons, medical/scientific/legal/security accuracy, or current evidence. |

## Capability verification

The default core profile exposes `elite_verify(check="capabilities")`; the legacy compatibility profile exposes `verify_capabilities_tool()`. Both exist because configured tools are not always callable tools.

For Zed, the orchestrator now prefers `context_servers` from `~/.config/zed/settings.json` and suppresses cross-IDE Gemini/Antigravity skills unless explicitly allowed by:

```bash
ELITE_ALLOW_CROSS_IDE_SKILLS=1
```

For exact active-session visibility, set:

```bash
ELITE_VISIBLE_MCPS="elite-reasoning,mcp-server-github"
ELITE_VISIBLE_SKILLS="arxiv,research-router"
```

This prevents recommending tools or skills that the active IDE agent cannot invoke.

## Required future benchmark loop

For every high-impact change, compare MCP-on vs MCP-off:

```text
Task → MCP-off result → MCP-on result → executable validation / judge / user rating → ROI report
```

Minimum metrics:

- task success
- regression preservation
- repeated mistake rate
- evidence quality
- tool-call count
- latency
- confidence calibration
- user usefulness rating

If the MCP increases tool calls and latency without improving these metrics, the rule/tool should be retired or narrowed.
