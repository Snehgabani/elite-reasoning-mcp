# Elite Reasoning MCP

**Model Context Protocol workflow memory, evaluation, and reasoning-safety layer for AI coding agents.**

<p align="center">
  <img src="assets/hero-banner.png" alt="Elite Reasoning MCP" width="100%">
</p>

<p align="center">
  <strong>Give coding agents a compact, evidence-gated workflow layer with trusted memory and local release verification.</strong>
</p>

<p align="center">
  <a href="https://github.com/Snehgabani/elite-reasoning-mcp/actions/workflows/ci.yml"><img src="https://github.com/Snehgabani/elite-reasoning-mcp/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/Snehgabani/elite-reasoning-mcp/actions/workflows/codeql.yml"><img src="https://github.com/Snehgabani/elite-reasoning-mcp/actions/workflows/codeql.yml/badge.svg" alt="CodeQL"></a>
  <a href="https://github.com/Snehgabani/elite-reasoning-mcp/actions/workflows/secret-scan.yml"><img src="https://github.com/Snehgabani/elite-reasoning-mcp/actions/workflows/secret-scan.yml/badge.svg" alt="Secret Scan"></a>
  <a href="https://github.com/Snehgabani/elite-reasoning-mcp/actions/workflows/scorecard.yml"><img src="https://github.com/Snehgabani/elite-reasoning-mcp/actions/workflows/scorecard.yml/badge.svg" alt="OpenSSF Scorecard"></a>
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
  <a href="#-core-tools-default">Core Tools</a> •
  <a href="#-configuration">Config</a> •
  <a href="#-security--trust">Security</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## Why Elite Reasoning?

Coding agents often miss one requirement in a long request, claim completion without evidence, or repeat a previously identified mistake. Elite Reasoning provides a local [Model Context Protocol](https://modelcontextprotocol.io/) workflow layer that makes requirements explicit, records execution state, retrieves scoped memory, and checks completion evidence.

The default product is intentionally narrow: it compiles a task contract, lets the host perform the work, and returns explicit verification results. Deterministic checks can establish only the behavior they inspect; they do not prove that generated code is correct or secure. Experimental reasoning techniques remain available through non-default profiles and are not part of the core product claim.

> **Install locally, connect an MCP-compatible client, and inspect exactly what was checked, what failed, and what remains unknown.**

<!-- BEGIN GENERATED CLAIMS -->
### Current evidence summary

> Claims below are generated from [`claims.yml`](claims.yml). Implementation checks describe covered behavior; the internal pilot is not evidence of broad model improvement.

- **Internal fixture pilot constraint pass rate** — A seven-case internal fixture pilot observed 5/7 treatment drafts and 0/7 baseline drafts passing all extracted constraints. The bundled drafts were hand-authored protocol fixtures—not live randomized model outputs—and the primary exact McNemar result (p=0.0625) was not significant at alpha=0.05. _Status: internal pilot; replication: not independently replicated._
- **Deterministic syntax and security checks** — Local deterministic checks cover Python syntax and selected unsafe patterns. Their scope is limited to implemented rules; passing them does not prove correctness or absence of vulnerabilities. _Status: implementation verified; replication: repository tests only._
- **Exact-quote grounding behavior** — The grounding path checks exact quote occurrence against retrieved evidence and exposes degraded or uncertain states. Quote matching alone does not prove source quality or full claim entailment. _Status: implementation verified; replication: repository tests only._

<!-- END GENERATED CLAIMS -->

### Who This Is For

- Developers using Cursor, Claude Desktop, Windsurf, or VS Code who want explicit requirement and completion checks.
- Teams evaluating lower-cost coding models that need auditable constraints and evidence rather than unsupported quality scores.
- AI engineers building agent loops that need a compact typed MCP workflow and local-first state.
- Maintainers who want scoped memory, release diagnostics, and transparent limitations.

### The Problem & The Solution

| Common agent failure | Core Elite behavior |
|:---|:---|
| A requirement is overlooked | Compiles explicit constraints linked to the task |
| Completion is claimed without validation | Requests test, syntax, grounding, or outcome evidence |
| A previous mistake is repeated | Retrieves approved, scoped anti-pattern memory |
| A citation cannot be supported | Returns degraded or uncertain grounding instead of inventing evidence |
| Multi-step work gets lost | Records an ordered, durable workflow when persistence is enabled |
| A check is outside the verifier's scope | Reports the limitation rather than treating it as proof of correctness |

---

## ⚡ Quick Start

### One-Line Install

```bash
pip install elite-reasoning-mcp
```

For an isolated CLI installation:

```bash
uv tool install elite-reasoning-mcp

# Verify the actual binary your IDE will run
elite-reasoning-mcp --version
elite-reasoning-mcp doctor --json

# Run an offline bad-draft → corrected-draft verification demo
elite-reasoning-mcp demo

# Preview a safe standalone upgrade command
elite-reasoning-mcp upgrade --dry-run
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
        "ELITE_BRAIN_DIR": "~/.elite-reasoning/brain",
        "ELITE_TOOL_PROFILE": "core"
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
        "ELITE_BRAIN_DIR": "~/.elite-reasoning/brain",
        "ELITE_TOOL_PROFILE": "core"
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
      ELITE_TOOL_PROFILE: core
```

### Activate the Pipeline

Add this to your IDE's system prompt (e.g., `~/.gemini/GEMINI.md` or Cursor Rules):

```markdown
## ⚡ RULE #0 — ELITE MCP PIPELINE

For every non-trivial prompt, call this first:

elite_prepare(user_prompt="<the user's exact message>")

Use ONLY `allowed_tools`, in `playbook` order. Do not pick other MCP tools.

If the playbook requires evidence:
elite_verify(check="evidence", query="<question>")

Do the host_work step (write the answer or patch).

Then the independent gate:
elite_verify(check="outcomes", run_id="<run id>", draft="<your draft>")

If action=REPEAT: fix unmet outcomes and verify again. Do not answer the user yet.
If action=DONE: you may answer.

Skip tool calls for trivial acknowledgements like "ok", "thanks", "yes", "no".
```

**That's it.** Restart your IDE and every conversation automatically benefits from the reasoning pipeline.

---

## 🚀 Features

### 🧠 Evidence-Gated Workflow
When the IDE calls `elite_prepare`, the server creates a durable plan with risk-aware validation gates, trusted memory context, and a compact typed response. `elite_progress` rejects out-of-order completion and terminal claims without evidence. Verification calls distinguish `PASS`, `FAIL`, `UNKNOWN`, and `NOT_CHECKED`; evidence IDs are bound to a SHA-256 digest of the exact draft, code, query, command, or Git working-tree snapshot checked. Tested code workflows cannot return `DONE` from prose such as “pytest passed”: they require persisted command evidence bound to the current repository state, and scope policies include tracked and untracked changed files.

### 🛡️ Anti-Pattern Memory
Past mistakes are recorded with root-cause analysis and automatically surfaced when similar patterns appear. Your AI literally learns from its errors.

### 📊 Confidence Calibration
Track prediction accuracy with proper Brier scores. Know when your AI is overconfident vs. well-calibrated. Every prediction gets a confidence score and outcome tracking.

### ⚖️ Decision Council
Critical decisions get a 5-perspective adversarial review — optimist, pessimist, pragmatist, innovator, and devil's advocate — before committing.

### 🔒 Prevention Rules
Custom auto-triggered rules for your workflow. Define patterns that should trigger warnings, blocks, or automatic corrections. Rules self-improve through a learning pipeline.

### 📈 8-Layer Middleware Chain
Every tool call passes through usage logging, latency measurement, prevention rules, anti-pattern injection, periodic scanning, cost tracking, fallback guidance, and real transient retries. Structured gateway responses retain a stable `warnings` field rather than receiving ad-hoc text wrappers.

### 🧪 Risk Analysis
FMEA (Failure Mode & Effects Analysis), Swiss Cheese audits, smoke test gates, and pre-mortem simulations — all built-in, all callable as MCP tools.

### 💾 Persistent Memory
Cross-session knowledge stays scoped, trust-weighted, and privacy-gated. Secret-like content is redacted before storage; low-trust, sensitive, expired, and remotely imported items remain quarantined until an explicit approval action promotes them. Sensitive records cannot be promoted, and `elite_memory(action="forget")` permanently removes a selected local item.

### 🧭 Workflow Flight Recorder
`elite_prepare` records a durable execution contract, while `elite_progress` requires ordered evidence before completion. This gives agent work a recoverable audit trail without pretending the server executed the task itself.

### 🏥 Release Doctor And Local Monitoring
`elite_verify(check="doctor")` checks runtime identity, protocol version, dependencies, DB schema, capability routing, exposed tool count, active IDE mismatch, and release blockers before shipping. `elite_admin(action="monitoring")` returns local aggregate latency, workflow, and memory health without exporting prompt content.

### 🧪 Eval Harness Exports
The explicit `legacy` profile retains `export_eval_harness` for optional Promptfoo, DeepEval, and Inspect AI scaffolds. The default profile stays compact so agents can select the correct workflow actions reliably.

---

## 🏗️ Architecture

```
Your Task
    ↓
elite_prepare  →  playbook + expected outcomes + allowed_tools
    ↓
host follows playbook (usually 1–2 elite_verify calls, then host_work)
    ↓
elite_verify(check="outcomes")  →  DONE or REPEAT
    ↓
if REPEAT: fix unmet items and verify again (do not answer yet)
    ↓
┌──────────────────────────────────────────────┐
│ Local-first telemetry and memory boundaries    │
│ Metadata by default; raw retention opt-in      │
│ Remote memory remains quarantined until review │
└──────────────────────────────────────────────┘
```

---

## 🔧 Core Tools (default)

The default v2 profile intentionally exposes five task-oriented tools. This improves tool selection, output-contract reliability, and safety for every MCP client.

| Tool | Description |
|:-----|:------------|
| `elite_prepare` | First call every non-trivial prompt. Personalized playbook, expected outcomes, allowed tools. Not the answer. |
| `elite_progress` | Optional flight recorder. Not required to finish if outcomes verify. |
| `elite_verify` | Independent gate. `check=outcomes` returns REPEAT or DONE. Also evidence/syntax/tests. |
| `elite_memory` | Search, write, approve low-trust memory, or permanently forget a local memory item. |
| `elite_admin` | Inspect runtime identity, privacy policy, and local aggregate monitoring. |

### Legacy Catalog (explicit opt-in)

Existing installations can retain the full legacy tool catalog by installing `elite-reasoning-mcp[legacy]` and setting `ELITE_TOOL_PROFILE=legacy`. It is not the default because a broad discovery surface makes selection less reliable for agents, and its graph/model dependencies are intentionally excluded from the dependency-light core installation. The legacy profile includes the following 90+ tools and resources:

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

<details>
<summary><strong>Unified Cognitive Singularity & MIX MCP Pipeline (42)</strong></summary>

| Tool | Description |
|:-----|:------------|
| `execute_mix` | 9-Stage Supreme Cognitive Pipeline (Meta-Routing + Bias Scan + Dynamic Topology + PRM Invariant Gate + PoW) |
| `elite_reason` | High-deliberation reasoning execution pipeline |
| `execute_singularity` | Drop-in backward-compatible entry point for `execute_mix` |
| `prm_verify_step` | Process Reward Model step verification (Math invariants, AST syntax, quantifier biases) |
| `compose_reasoning_topology` | Dynamic reasoning DAG topology composition via Self-Discover framework |
| `think_on_graph_search` | Think-on-Graph (ToG) beam search over knowledge graphs |
| `verify_argument` | Syllogism and logical fallacy verification with deterministic fail-safes |
| `expert_panel` | Concurrent dialectical viewpoint evaluation across domain expert personas |
| `repo_search` | Codebase AST property graph search for symbol definitions and references |
| `repo_impact_map` | Blast radius, dependency tree, and impacted test analysis for code changes |
| `apply_reasoning_diff` | Physical disk write barrier gated by HMAC-SHA256 authorization and AST syntax pre-flight |
| `fuzz_symbol` | Property-based testing for code symbols discovering edge case failures |
| `god_tier_reasoning` | N-candidate parallel reasoning with Constitutional Rubric Rejection Sampling |
| `hard_reason` | Language Agent Tree Search (LATS) with executable verifiers |
| `dual_process_route` | System 1 (fast heuristic) vs System 2 (deep deliberate graph) dynamic router |
| `self_rag_evaluate` | Self-RAG reflection token evaluation (relevance, support, utility) |
| `skeleton_of_thought_generate` | Concurrent parallel expansion of structured skeleton points |
| `live_web_search` | Multi-engine live search with semantic re-ranking |
| `red_team_attack` | Adversarial counter-hypothesis and failure mode stress-testing |
| `epistemic_verify` | Atomic proposition deconstruction and authoritative verification |
| `triangulate_claim` | Multi-source cross-referencing and verification |
| `deep_read` | Full markdown extraction, chunking, and semantic filtering on URLs |
| `temporal_verify` | Historical and temporal validity verification against timestamped records |
| `devils_advocate` | Dialectical revision loop challenging assumptions |
| `epistemic_research` | Multi-phase deep epistemic research with provenance tracking |
| `verify_claims` | Automated claim extraction and verification pipeline |
| `deep_research_report` | Stanford STORM Deep Research Engine with Table of Contents and citations |
| `autonomous_research` | Iterative research loop decomposing complex questions |
| `candidate_search` | Multi-solution candidate generation and automated scoring |
| `verify_candidate` | Candidate solution verification via sandbox execution or rubric |
| `reflexion_fix` | Minimal repair plan generation with automated lesson extraction |
| `compile_skills` | Compiles successful traces into task-specific exemplar prompts |
| `get_workspace_file` | Reads workspace files directly into reasoning state |
| `get_live_watcher_status` | Real-time live telemetry, active cognitive graphs, and watchdog health status |

</details>

Plus **7 MCP Resources** (`elite://profile`, `elite://anti_patterns`, `elite://decisions`, `elite://quality`, `elite://health`, `elite://goals`, `elite://benchmarks`) for real-time dashboards.

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|:---------|:--------|:------------|
| `ELITE_BRAIN_DIR` | `~/.elite-reasoning/brain` | Where to store persistent memory |
| `ELITE_TOOL_PROFILE` | `core` | `core` exposes five typed gateway tools; `legacy` enables the compatibility catalog. |
| `ELITE_TELEMETRY_MODE` | `metadata` | `off`, `metadata`, `summary`, or `raw`; raw requires a second opt-in. |
| `ELITE_ALLOW_RAW_TELEMETRY` | unset | Must be `1` before `ELITE_TELEMETRY_MODE=raw` is honored. |
| `ELITE_ALLOW_RAW_PROMPT_STORAGE` | unset | Must be `1` to retain redacted raw prompts; otherwise prompts are hashed and withheld. |
| `ELITE_SYNC_ALLOWED_HOSTS` | localhost only | Comma-separated approved sync hosts. |
| `ELITE_SYNC_ALLOW_NETWORK` | unset | Must be `1` for approved non-local sync hosts. |
| `ELITE_SYNC_ALLOW_OUTBOUND` | unset | Must be `1` before legacy sync can push local decisions or anti-patterns. |
| `ELITE_SYNC_BIND_ALL_INTERFACES` | unset | Required with a sync API key before the optional hub can bind beyond localhost. |
| `SYNC_USER_KEYS_JSON` | unset | Optional sync-hub JSON mapping of user IDs to distinct API keys for auditable multi-user attribution. |
| `SYNC_SINGLE_USER_ID` | `single-user` | Server-side actor label for a single-user hub using `SYNC_API_KEY`. |
| `ELITE_SYNC_ENABLE_LLM_JUDGE` | unset | Required with `GEMINI_API_KEY` before the hub sends submissions to an external LLM judge. |
| `ELITE_ENABLE_LEGACY_INTERCEPTOR` | `0` | Enable legacy monkey-patch interceptor |
| `ELITE_GEMINI_BASE_URL` | (built-in) | HTTPS Gemini endpoint; a non-Google host also requires `ELITE_ALLOW_CUSTOM_GEMINI_ENDPOINT=1`. |

The local profile is created with owner-only permissions at `~/.elite-reasoning/config.json`; it is not read from the repository checkout and must never be committed. Neutral configuration and team-memory shapes are available in [docs/examples/local-profile.example.json](docs/examples/local-profile.example.json) and [docs/examples/team-memory.example.json](docs/examples/team-memory.example.json). Keep credentials in process environment variables or an OS keychain, not in JSON.

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
# Run all tests
ELITE_BRAIN_DIR=/tmp/elite-test uv run pytest tests/ -v --tb=short

# Run the full release gate: tests, lint, types, high-severity scan,
# package privacy/content inspection, wheel CLI, and MCP smoke
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
- ✅ stdio MCP protocol identity, structured output, and `isError=true` failures
- ✅ privacy-safe telemetry, secret migration, approved sync, and memory quarantine
- ✅ ordered workflow evidence, prevention events, retry, fallback, and local monitoring
- ✅ Quality-gated memory quarantine
- ✅ Release doctor and eval harness exporters

---

## 🔐 Security & Trust

Elite Reasoning MCP is local-first by default: memory is stored under `ELITE_BRAIN_DIR`, telemetry stores metadata rather than prompt content, and external API access is opt-in through environment configuration.

The default profile does not expose network sync tools. In the explicit legacy profile, every sync request requires `confirm=true`, an allowlisted endpoint, redirect blocking, and environment grants for external or outbound traffic. The optional sync hub binds to localhost by default; external binding needs configured credentials and `ELITE_SYNC_BIND_ALL_INTERFACES=1`. For multi-user deployments, configure distinct credentials with `SYNC_USER_KEYS_JSON`; the hub derives contributor attribution from the credential and never trusts a caller-supplied user ID. Imported remote records are stored as low-trust quarantined memory until an operator explicitly approves them. External LLM judging is disabled unless both `GEMINI_API_KEY` and `ELITE_SYNC_ENABLE_LLM_JUDGE=1` are set.

Public repository hardening includes:
- `SECURITY.md` with supported versions, private vulnerability reporting, and memory/privacy boundaries
- Dependabot for Python, GitHub Actions, and telemetry UI dependencies
- CodeQL scanning for Python security issues
- Dependency Review on pull requests
- OpenSSF Scorecard visibility for supply-chain posture
- Immutable GitHub Action and Docker image pins, with Dependabot update coverage
- GitHub build provenance and PyPI digital attestations for release distributions
- An allowlisted source distribution plus a release gate that rejects local profiles, generated UI output, databases, and credential-like files
- A checksum-verified, read-only Gitleaks workflow that scans full Git history and the checked-out files with redacted findings
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
