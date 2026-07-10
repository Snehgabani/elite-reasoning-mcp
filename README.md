# Elite Reasoning MCP

**Model Context Protocol workflow memory, evaluation, and reasoning-safety layer for AI coding agents.**

<p align="center">
  <img src="assets/hero-banner.png" alt="Elite Reasoning MCP" width="100%">
</p>

<p align="center">
  <strong>Make any LLM think harder, reason better, and stop repeating preventable mistakes.</strong>
</p>

<p align="center">
  <a href="https://github.com/Snehgabani/elite-reasoning-mcp/actions/workflows/ci.yml"><img src="https://github.com/Snehgabani/elite-reasoning-mcp/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/elite-reasoning-mcp/"><img src="https://img.shields.io/pypi/v/elite-reasoning-mcp?style=flat-square&color=blue" alt="PyPI"></a>
  <a href="https://pypi.org/project/elite-reasoning-mcp/"><img src="https://img.shields.io/pypi/dm/elite-reasoning-mcp?style=flat-square&color=green" alt="Downloads"></a>
  <a href="https://pypi.org/project/elite-reasoning-mcp/"><img src="https://img.shields.io/pypi/pyversions/elite-reasoning-mcp?style=flat-square" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Snehgabani/elite-reasoning-mcp?style=flat-square" alt="License"></a>
  <a href="SECURITY.md"><img src="https://img.shields.io/badge/security-policy-brightgreen?style=flat-square" alt="Security Policy"></a>
  <a href="https://github.com/Snehgabani/elite-reasoning-mcp/stargazers"><img src="https://img.shields.io/github/stars/Snehgabani/elite-reasoning-mcp?style=flat-square" alt="Stars"></a>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-features">Features</a> •
  <a href="#who-this-is-for">Use Cases</a> •
  <a href="#%EF%B8%8F-architecture">Architecture</a> •
  <a href="#-90-tools">All Tools</a> •
  <a href="#-configuration">Config</a> •
  <a href="#-security--trust">Security</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## Why Elite Reasoning?

Every AI coding assistant makes the **same mistakes twice**. Elite Reasoning fixes that.

It's a [Model Context Protocol](https://modelcontextprotocol.io/) server for AI IDEs and coding agents. It wraps around any LLM — GPT, Claude, Gemini, open-source — and adds a **persistent reasoning layer** with workflow flight recording, anti-pattern memory, decision tracking, confidence calibration, release doctor checks, eval harness exports, and self-improving prevention rules.

> **One install. Zero config. Works with Cursor, Antigravity, VS Code + Continue, Windsurf, and any MCP-compatible IDE.**

### Who This Is For

- Developers who use Cursor, Claude Desktop, Gemini CLI, VS Code + Continue, Windsurf, or another MCP-compatible AI IDE.
- AI coding-agent users who want persistent memory without blindly injecting stale, low-trust, or sensitive context.
- Maintainers who need auditable multi-step execution, release gates, risk checks, and repeatable eval scaffolds.
- Teams building agentic development workflows that need reasoning safety, confidence calibration, and workflow evidence.

### The Problem

| Without Elite Reasoning | With Elite Reasoning |
|:---|:---|
| LLM forgets past mistakes | ✅ Anti-pattern memory prevents repeats |
| No confidence tracking | ✅ Brier-scored calibration per prediction |
| Generic responses | ✅ Intent-classified, complexity-scored routing |
| No decision audit trail | ✅ Every architectural decision logged + searchable |
| Manual quality checks | ✅ Automated pre-commit audits + FMEA risk gates |
| Multi-step work gets lost | ✅ `workflow_run` creates durable evidence + validation gates |
| Memory can poison context | ✅ Trust/confidence/privacy gates quarantine risky memories |

---

## ⚡ Quick Start

### One-Line Install

```bash
pip install elite-reasoning-mcp
```

For an isolated CLI installation:

```bash
uv tool install elite-reasoning-mcp
```

### Add to your IDE

**Antigravity / Gemini CLI** (`~/.gemini/config/mcp_config.json`):
```json
{
  "mcpServers": {
    "elite-reasoning": {
      "command": "elite-reasoning-mcp",
      "args": [],
      "env": {
        "ELITE_BRAIN_DIR": "~/.elite-reasoning/brain"
      }
    }
  }
}
```

**Cursor** (`.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "elite-reasoning": {
      "command": "elite-reasoning-mcp",
      "env": {
        "ELITE_BRAIN_DIR": "~/.elite-reasoning/brain"
      }
    }
  }
}
```

**VS Code + Continue** (`~/.continue/config.yaml`):
```yaml
mcpServers:
  - name: elite-reasoning
    command: elite-reasoning-mcp
    env:
      ELITE_BRAIN_DIR: ~/.elite-reasoning/brain
```

### Activate the Pipeline

Add this to your IDE's system prompt (e.g., `~/.gemini/GEMINI.md` or Cursor Rules):

```markdown
## ⚡ RULE #0 — ELITE MCP PIPELINE

For non-trivial build, debug, research, audit, or release tasks, start with:

orchestrate_request_tool(user_prompt="<the user's exact message>")

For multi-step work that must be auditable, then create a durable run:

workflow_run(user_prompt="<the user's exact message>")

Skip tool calls for trivial acknowledgements like "ok", "thanks", "yes", "no".
```

**That's it.** Restart your IDE and every conversation automatically benefits from the reasoning pipeline.

---

## 🚀 Features

### 🧠 Reasoning Pipeline
Every prompt flows through an intelligent routing system that classifies intent (13 categories), scores complexity (1-5), selects thinking mode, and checks anti-patterns — before your LLM even sees the task.

### 🛡️ Anti-Pattern Memory
Past mistakes are recorded with root-cause analysis and automatically surfaced when similar patterns appear. Your AI literally learns from its errors.

### 📊 Confidence Calibration
Track prediction accuracy with proper Brier scores. Know when your AI is overconfident vs. well-calibrated. Every prediction gets a confidence score and outcome tracking.

### ⚖️ Decision Council
Critical decisions get a 5-perspective adversarial review — optimist, pessimist, pragmatist, innovator, and devil's advocate — before committing.

### 🔒 Prevention Rules
Custom auto-triggered rules for your workflow. Define patterns that should trigger warnings, blocks, or automatic corrections. Rules self-improve through a learning pipeline.

### 📈 8-Layer Middleware Chain
Every tool call passes through telemetry → anti-pattern injection → prevention rules → cost tracking → usage logging → latency budgets → retry → fallback — with zero config.

### 🧪 Risk Analysis
FMEA (Failure Mode & Effects Analysis), Swiss Cheese audits, smoke test gates, and pre-mortem simulations — all built-in, all callable as MCP tools.

### 💾 Persistent Memory
Cross-session knowledge graph with temporal confidence decay, semantic search, decision audit trails, and quality-gated memory context. Your AI remembers what it learned last week without blindly injecting low-trust or sensitive content.

### 🧭 Workflow Flight Recorder
`workflow_run` turns complex work into a persisted execution contract: intent, complexity, budget tier, relevant memory, evidence requirements, validation gates, confidence, and step status.

### 🏥 Release Doctor
`elite_doctor` checks version, dependencies, DB schema, capability routing, exposed tool count, active IDE mismatch, and release blockers before shipping.

### 🧪 Eval Harness Exports
`export_eval_harness` generates optional Promptfoo, DeepEval, and Inspect AI scaffolds for MCP-on/MCP-off comparisons without adding hard runtime dependencies.

---

## 🏗️ Architecture

```
Your Prompt
    ↓
orchestrate_request_tool (complex-task routing)
    ↓
┌──────────────────────────────────────────────┐
│  🎯 Intent Classifier    → 13 categories     │
│  📊 Complexity Scorer    → 1-5 scale         │
│  🧠 Thinking Mode        → convergent/div.   │
│  🛡️ Anti-Pattern Check   → Past mistake scan  │
│  ⚡ Prevention Engine    → Custom auto-rules  │
│  🔀 MCP/Skill Router    → Specialized tools   │
└──────────────────────────────────────────────┘
    ↓
Execution Plan (returned to LLM)
    ↓
LLM follows plan → Better output
    ↓
┌──────────────────────────────────────────────┐
│  8-Layer Middleware Chain (wraps every tool)  │
│  Telemetry → Injection → Prevention →        │
│  Cost → Usage → Latency → Retry → Fallback  │
└──────────────────────────────────────────────┘
    ↓
Results recorded → Learning loop improves next time
```

---

## 🔧 90+ Tools

<details>
<summary><strong>Core Pipeline (3)</strong></summary>

| Tool | Description |
|:-----|:------------|
| `orchestrate_request_tool` | Master routing — fires on every prompt, classifies intent, routes to tools |
| `reasoning_preflight` | Pre-flight checklist for complex tasks |
| `assess_confidence` | Score confidence before committing to a plan |

</details>

<details>
<summary><strong>Workflow, Release & Eval (8)</strong></summary>

| Tool | Description |
|:-----|:------------|
| `workflow_run` | Create a durable evidence-gated execution contract |
| `workflow_status` | Inspect persisted workflow run status |
| `workflow_update_step` | Attach validation evidence to workflow steps |
| `elite_doctor` | Human-readable release-readiness health check |
| `elite_doctor_json` | Structured release-readiness report |
| `export_eval_harness` | Generate Promptfoo, DeepEval, and Inspect AI eval scaffolds |
| `remember_context` | Store quality-gated scoped memory |
| `memory_context_pack` | Retrieve trusted memory context for a task |

</details>

<details>
<summary><strong>Quality & Anti-Patterns (6)</strong></summary>

| Tool | Description |
|:-----|:------------|
| `check_anti_patterns` | Semantic search over past mistakes |
| `record_mistake` | Log mistakes with root cause analysis |
| `record_quality_score` | Score output quality (1-10) |
| `get_quality_trend` | Track quality trends over time |
| `pre_commit_audit` | Audit code before delivering |
| `bias_scan` | Detect cognitive biases in reasoning |

</details>

<details>
<summary><strong>Decision Making (6)</strong></summary>

| Tool | Description |
|:-----|:------------|
| `record_decision` | Log architectural decisions with rationale |
| `search_decisions` | Query past decisions (FTS + semantic) |
| `decision_council_review` | 5-perspective adversarial review |
| `adopt_vs_build` | Build-or-adopt analysis framework |
| `socratic_challenge` | Challenge your own plan's assumptions |
| `after_action_review` | Post-mortem structured review |

</details>

<details>
<summary><strong>Risk Analysis (5)</strong></summary>

| Tool | Description |
|:-----|:------------|
| `fmea_analysis` | Failure Mode & Effects Analysis |
| `fmea_risk_gate` | Risk threshold gate (block if RPN too high) |
| `smoke_test_gate` | Pre-deploy smoke test |
| `swiss_cheese_audit` | Multi-layer safety audit (Reason model) |
| `simulate_future_regrets` | Pre-mortem / regret simulation |

</details>

<details>
<summary><strong>Confidence & Calibration (3)</strong></summary>

| Tool | Description |
|:-----|:------------|
| `calibration_predict` | Log predictions with confidence % |
| `calibration_resolve` | Record actual outcomes |
| `calibration_score` | Brier score accuracy report |

</details>

<details>
<summary><strong>Memory & Knowledge Graph (5)</strong></summary>

| Tool | Description |
|:-----|:------------|
| `ingest_context` | Store cross-session knowledge |
| `memory_search_context` | Semantic search over memory |
| `memory_sync_decisions` | Persist decisions to long-term memory |
| `memory_sync_mistakes` | Persist mistakes to memory |
| `query_temporal_graph` | Knowledge graph queries with time decay |

</details>

<details>
<summary><strong>Goals & Benchmarks (7)</strong></summary>

| Tool | Description |
|:-----|:------------|
| `set_goal` | Define goals with key results |
| `check_goals` | Review active goals |
| `update_goal` | Update goal progress |
| `archive_goal` / `delete_goal` | Lifecycle management |
| `benchmark_track` | Track performance benchmarks |
| `get_tool_usage_stats` | Tool usage analytics |

</details>

<details>
<summary><strong>Learning & Autonomy (12)</strong></summary>

| Tool | Description |
|:-----|:------------|
| `record_prompt_intent` | Track prompt patterns |
| `analyze_prompt_sequence` | Session analysis |
| `get_user_thinking_model` | Cognitive model of user patterns |
| `update_thinking_pattern` | Update learned patterns |
| `register_prevention_rule` | Create custom auto-rules |
| `list_prevention_rules` | View active rules |
| `predictive_prevention` | Predict failures before they happen |
| `autonomous_scan` | Self-improvement scan |
| `self_diagnose` | System health diagnostic |
| `get_autonomous_status` | Autonomy rate and gap report |
| `generate_autonomous_goals` | Auto-generate improvement goals |
| `record_missed_detection` | Log when the system should have caught something |

</details>

<details>
<summary><strong>Quantitative Reasoning (5)</strong></summary>

| Tool | Description |
|:-----|:------------|
| `bayesian_update` | Bayesian probability updates |
| `calculate_expected_value` | Expected value calculations |
| `compound_growth` | Compound growth modeling |
| `five_whys` | Root cause analysis (5 Whys) |
| `validate_predictions` | Validate prediction batches |

</details>

<details>
<summary><strong>Collaboration (5)</strong></summary>

| Tool | Description |
|:-----|:------------|
| `get_user_profile` | User preference profile |
| `update_user_config` | Update user settings |
| `list_team_users` | Team user management |
| `share_skill` | Share learned skills |
| `sync_team_memory` | Sync memory across team |

</details>

<details>
<summary><strong>Natural Language Verbs (6)</strong></summary>

| Tool | Description |
|:-----|:------------|
| `plan` | Create structured plans |
| `analyze` | Deep analysis mode |
| `audit` | Comprehensive audit |
| `predict` | Make tracked predictions |
| `learn` | Learn from outcomes |
| `introspect` | Self-reflection on reasoning |

</details>

<details>
<summary><strong>Hypothesis & Prospective (5)</strong></summary>

| Tool | Description |
|:-----|:------------|
| `record_hypothesis` | Log testable hypotheses |
| `resolve_hypothesis` | Record hypothesis outcomes |
| `record_prospective_failure` | Pre-register potential failures |
| `resolve_prospective_failure` | Record failure outcomes |
| `search_thinking_patterns` | Search learned patterns |

</details>

Plus **7 MCP Resources** (`elite://profile`, `elite://anti_patterns`, `elite://decisions`, `elite://quality`, `elite://health`, `elite://goals`, `elite://benchmarks`) for real-time dashboards.

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|:---------|:--------|:------------|
| `ELITE_BRAIN_DIR` | `~/.elite-reasoning/brain` | Where to store persistent memory |
| `ELITE_ENABLE_LEGACY_INTERCEPTOR` | `0` | Enable legacy monkey-patch interceptor |
| `ELITE_GEMINI_BASE_URL` | (built-in) | Custom Gemini API endpoint |

### Development Setup

```bash
# Clone the repo
git clone https://github.com/Snehgabani/elite-reasoning-mcp.git
cd elite-reasoning-mcp

# Install with dev dependencies
uv sync --extra dev

# Run the release gate used by CI
uv run python scripts/release_check.py

# Build package
uv build
```

---

## 🧪 Testing

```bash
# Run all tests (229 tests)
ELITE_BRAIN_DIR=/tmp/elite-test uv run pytest tests/ -v --tb=short

# Run the full release gate: tests, ruff, focused pyright, build, MCP smoke
uv run python scripts/release_check.py

# Run with coverage
uv run pytest tests/ --cov=core --cov-report=html
```

The test suite covers:
- ✅ Persistent store (CRUD, FTS, graph, goals, benchmarks)
- ✅ Graph store (nodes, edges, temporal queries, hypotheses)
- ✅ Connection pooling and stale connection recovery
- ✅ FTS sanitization (injection prevention)
- ✅ Workflow flight recorder and MCP tool exposure
- ✅ Quality-gated memory quarantine
- ✅ Release doctor and eval harness exporters

---

## 🔐 Security & Trust

Elite Reasoning MCP is local-first by default: memory is stored under `ELITE_BRAIN_DIR`, and external API access is opt-in through environment configuration.

Public repository hardening includes:
- `SECURITY.md` with supported versions, private vulnerability reporting, and memory/privacy boundaries
- Dependabot for Python, GitHub Actions, and telemetry UI dependencies
- CodeQL scanning for Python security issues
- Dependency Review on pull requests
- OpenSSF Scorecard visibility for supply-chain posture
- Immutable GitHub Action and Docker image pins, with Dependabot update coverage
- GitHub build provenance and PyPI digital attestations for release distributions
- Release-gate evidence via `scripts/release_check.py`

Security reports should use [GitHub private vulnerability reporting](https://github.com/Snehgabani/elite-reasoning-mcp/security/advisories/new), not public issues.

For the next tracking and monitoring layer, see the [Elite Telemetry Roadmap](docs/elite_telemetry_roadmap.md).

---

## 🤝 Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md), [GOVERNANCE.md](GOVERNANCE.md), and the security boundaries in [SECURITY.md](SECURITY.md).

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Run** the release gate (`uv run python scripts/release_check.py`)
4. **Document** MCP behavior, privacy impact, and validation evidence in your PR
5. **Commit** your changes (`git commit -m 'feat: add amazing feature'`)
6. **Push** to the branch (`git push origin feature/amazing-feature`)
7. **Open** a Pull Request

### Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` — New features
- `fix:` — Bug fixes
- `chore:` — Maintenance
- `docs:` — Documentation

---

## 📄 License

MIT © [Sneh Gabani](https://github.com/Snehgabani)

---

<p align="center">
  <sub>Built for the AI-native developer workflow</sub>
</p>
<p align="center">
  <a href="https://github.com/Snehgabani/elite-reasoning-mcp/stargazers">Star us on GitHub</a> •
  <a href="https://pypi.org/project/elite-reasoning-mcp/">View on PyPI</a> •
  <a href="https://github.com/Snehgabani/elite-reasoning-mcp/issues">Report a Bug</a>
</p>
