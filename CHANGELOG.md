# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.1] - 2026-07-04

### Added
- Security policy, support policy, code of conduct, governance notes, and citation metadata for public contribution readiness.
- Dependabot, CodeQL, dependency-review, and OpenSSF Scorecard workflows for supply-chain and repository security visibility.
- Discussion templates and stronger issue/PR templates with MCP runtime, privacy, and release-gate evidence fields.

### Changed
- Improved README and package metadata for Model Context Protocol, AI IDE, coding-agent, workflow-memory, and evaluation-harness discoverability.
- Hardened GitHub Actions workflow permissions and concurrency defaults.

## [1.2.0] - 2026-07-04

### Added
- `workflow_run`, `workflow_status`, and `workflow_update_step` tools for durable, evidence-gated task flight recording.
- Quality-gated memory tools: `remember_context` and `memory_context_pack` with trust, confidence, scope, expiry, and privacy quarantine.
- `elite_doctor` and `elite_doctor_json` release-readiness health checks.
- `export_eval_harness` for optional Promptfoo, DeepEval, and Inspect AI eval scaffolds without adding hard runtime dependencies.
- Release smoke tests for MCP tool exposure and workflow/memory/doctor behavior.
- `scripts/release_check.py` to run repeatable release gates.

### Fixed
- Health resource now imports the existing `core.memory.embedding.EmbeddingService`.
- Capability/profile IDE detection now uses the shared capability registry path.
- Team sync registration no longer hardcodes `antigravity`.
- Prompt sequence analysis now returns prompt rows for prompt quality trend tooling.
- Quality trend now exposes recent and older averages for autonomous scans.
- Thinking-pattern results now include backward-compatible key names.
- Decision council reviews now link to an actual decision journal entry.

### Removed
- Tracked `__pycache__`, SQLite sidecar, and diagnostic archive artifacts from source control.

## [1.1.2] - 2026-06-16

### Fixed
- `RetryMiddleware`: `time.sleep()` → `asyncio.sleep()` (was blocking async event loop)
- `FallbackMiddleware`: `time.time()` → `time.perf_counter()` (clock mismatch with `CallContext.started_at`)
- `PreventionRuleMiddleware`: Removed double wildcard emit (rules were firing twice)
- Legacy interceptor: `'on_prompt'` → `'prompt.received'` (stale event name)
- Removed unused `typing.Any` import (CI ruff lint fix)

## [1.1.1] - 2026-06-15

### Fixed
- Middleware chain now connected to all 73 registered tools via `middleware_setup.py`
- `OptimizationLoop` wired to `PeriodicScanMiddleware` for autonomous learning
- Prevention rule trigger map migrated to canonical events (`tool.before:*`, `prompt.received`)
- `FallbackMiddleware` and `RetryMiddleware` crash bugs (invalid `CallResult` schema)
- Wired `temporal_confidence`, `severity_inference`, and `trigger_learner` learning modules
- Fixed health resource to check `EmbeddingService`
- `main()` now reads `ELITE_BRAIN_DIR` environment variable
- `optimization_events` table added to `_init_db()`

### Removed
- `native_tools.py` (dead code with `shell=True` security risk)
- `registry.py` (dead `ActionRegistry` class)

### Security
- Removed dynamic SQL in `update_rule_lifecycle()` (parameterized queries only)
- Gemini URL now configurable via `ELITE_GEMINI_BASE_URL` env var

## [1.1.0] - 2026-06-14

### Added
- 8-layer middleware chain (telemetry, injection, prevention, cost, usage, latency, retry, fallback)
- Verb tools (`plan`, `analyze`, `audit`, `predict`, `learn`, `remember`, `introspect`)
- Memory bridge tools (`memory_sync_decisions`, `memory_sync_mistakes`, `memory_sync_rules`, `memory_search_context`)
- Knowledge graph with temporal edges
- `OptimizationLoop` scheduler with 5-trigger autonomy
- Docker support (`Dockerfile` + `docker-compose.yml`)
- Windows installer (`install.ps1`)
- Telemetry UI dashboard (Next.js)

## [1.0.0] - 2026-06-12

### Added
- Initial release with 66 MCP tools
- Anti-pattern memory with FTS5 search
- Decision tracking and search
- Confidence calibration with Brier scores
- Prevention rules engine
- Goal management with key results
- Quality scoring and trend tracking
- FMEA risk analysis
- 7 MCP resources
- Cross-platform install scripts
- PyPI package publishing
