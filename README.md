# 🧠 Elite Reasoning MCP

**Makes any LLM think harder, reason better, and never repeat mistakes.**

66 tools that upgrade your AI's output quality — works with any model (GPT-4, Claude, Gemini, open-source).

## What It Does

Every prompt you send goes through a reasoning pipeline that:

| Feature | What it does |
|---------|-------------|
| **Intent Classification** | Auto-detects if you're debugging, building, designing, deploying (13 categories) |
| **Complexity Scoring** | Rates 1-5 and adjusts reasoning depth |
| **Anti-Pattern Memory** | Remembers past mistakes and prevents repeats |
| **Confidence Calibration** | Tracks prediction accuracy with Brier scores |
| **Decision Council** | 5-perspective adversarial review for critical decisions |
| **FMEA Risk Analysis** | What can fail? How bad? How likely? |
| **Socratic Challenge** | Challenges its own assumptions before committing |
| **Prevention Rules** | Custom auto-triggered rules for your workflow |
| **Cross-Session Memory** | Persists knowledge across conversations |

## Quick Install

```bash
# 1. Clone this repo
git clone https://github.com/YOUR_USERNAME/elite-reasoning-mcp.git ~/.elite-reasoning

# 2. Run the installer
bash ~/.elite-reasoning/install.sh

# 3. Restart your IDE and start a new conversation
```

## Manual Install

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- An MCP-compatible IDE (Antigravity, Cursor, VS Code + Continue, etc.)

### Steps

1. **Clone the repo:**
```bash
git clone https://github.com/YOUR_USERNAME/elite-reasoning-mcp.git ~/.elite-reasoning
cd ~/.elite-reasoning
```

2. **Add to your IDE's MCP config** (`~/.gemini/config/mcp_config.json` or equivalent):
```json
{
  "mcpServers": {
    "elite-reasoning": {
      "command": "/Users/YOUR_USERNAME/.elite-reasoning/run_elite_mcp.sh"
    }
  }
}
```

3. **Add enforcement rule** to `~/.gemini/GEMINI.md`:
```markdown
## ⚡ RULE #0 — ELITE MCP PIPELINE

On EVERY user message, your FIRST tool call MUST be:

\```
call_mcp_tool(
  ServerName="elite-reasoning",
  ToolName="orchestrate_request_tool",
  Arguments={"user_prompt": "<the user's exact message>"}
)
\```

No exceptions except "ok", "thanks", "yes", "no".
```

4. **Restart your IDE** and start a new conversation.

## 66 Tools

<details>
<summary>Click to see all tools</summary>

### Core Pipeline
- `orchestrate_request_tool` — Master routing (fires on every prompt)
- `reasoning_preflight` — Pre-flight checklist for complex tasks
- `assess_confidence` — Score confidence before committing

### Quality
- `check_anti_patterns` — Check past mistakes
- `record_mistake` — Log mistakes with root cause
- `record_quality_score` — Score output quality
- `get_quality_trend` — Track quality over time
- `pre_commit_audit` — Audit code before delivering

### Decision Making
- `record_decision` — Log architectural decisions
- `search_decisions` — Query past decisions
- `decision_council_review` — 5-perspective adversarial review
- `adopt_vs_build` — Build or adopt analysis
- `socratic_challenge` — Challenge your own plan

### Risk Analysis
- `fmea_analysis` — Failure mode analysis
- `fmea_risk_gate` — Risk threshold gate
- `smoke_test_gate` — Smoke test before deploy
- `swiss_cheese_audit` — Multi-layer safety audit
- `simulate_future_regrets` — Pre-mortem analysis

### Confidence & Calibration
- `calibration_predict` — Log predictions with confidence
- `calibration_resolve` — Mark prediction outcomes
- `calibration_score` — Brier score report

### Memory
- `ingest_context` — Store cross-session knowledge
- `memory_search_context` — Retrieve past context
- `memory_sync_decisions` — Persist decisions
- `query_temporal_graph` — Knowledge graph queries

### Goals & Tracking
- `set_goal` / `check_goals` / `update_goal` — Goal management
- `benchmark_track` — Performance benchmarks
- `get_tool_usage_stats` — Tool usage analytics

### Learning
- `record_prompt_intent` — Track prompt patterns
- `analyze_prompt_sequence` — Session analysis
- `get_user_thinking_model` — User cognitive model
- `register_prevention_rule` — Custom auto-rules
- `autonomous_scan` — Self-improvement scan

...and 30+ more

</details>

## Architecture

```
Your Prompt
    ↓
orchestrate_request_tool (FIRST tool call)
    ↓
┌─────────────────────────────┐
│  Intent Classifier          │ → debug/build/design/deploy/...
│  Complexity Scorer          │ → 1-5 scale
│  Thinking Mode Selector     │ → convergent/divergent/analytical
│  Anti-Pattern Checker       │ → Past mistake lookup
│  Prevention Rule Engine     │ → Custom auto-triggered rules
│  MCP/Skill Router           │ → Route to specialized tools
└─────────────────────────────┘
    ↓
Execution Plan (returned to LLM)
    ↓
LLM follows plan → Better output
```

## License

MIT
