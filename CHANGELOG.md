# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.1] - 2026-08-01

### Fixed
- Default profile and legacy orchestration/sync paths no longer derive identity from the operating-system account name. Local profiles now use an anonymous default, while `ELITE_USER_ID` is an explicit pseudonym opt-in.
- Profile and health output no longer reveal local identifiers, configuration paths, or sync endpoints.
- `ELITE_BRAIN_DIR` and `--brain-dir` now expand `~` consistently; legacy launchers, diagnostics, archived helpers, and the telemetry UI no longer reference a developer-specific machine path.
- Quarantined memory promotion now requires `confirm=true`, matching the explicit-review boundary used for destructive memory actions.
- Docker Compose now starts Uvicorn rather than the stdio MCP entrypoint, persists the sync hub to the mounted volume, binds its published port to localhost, requires a sync key, and checks the authenticated health endpoint.

### Changed
- Docker images install the locked runtime environment through `uv sync --frozen`.
- Package metadata uses project maintainer attribution without a personal email address.
- Added privacy, path portability, memory-promotion, and CLI-path regression coverage, plus a versioned hardening roadmap.

## [2.0.0] - 2026-07-16

### Added
- Compact default `core` MCP profile with five typed, annotated gateway tools: `elite_prepare`, `elite_progress`, `elite_verify`, `elite_memory`, and `elite_admin`.
- Protocol runtime identity: the MCP initialize response now advertises the package version, and the doctor reports executable, package, protocol, and tool-profile diagnostics.
- Explicit local CLI commands for `--version`, `doctor`, and a confirmation-gated `upgrade` preview/run path.
- Ordered workflow completion controls: terminal statuses require evidence, later steps cannot complete before earlier steps, and workflow status is derived from step outcomes.
- Typed structured `warnings` fields so prevention and middleware feedback survives without breaking MCP output schemas.
- Privacy-safe local monitoring through `elite_admin(action="monitoring")`, exposing only aggregate latency, workflow, and memory health.
- Stdio protocol tests for server identity, compact discovery, structured output, and `isError=true` tool failures.

### Changed
- The default public surface is now five task-oriented tools. The 90+ tool catalog and resources are available only with `ELITE_TOOL_PROFILE=legacy`.
- Tool errors now become sanitized typed MCP failures instead of successful-looking text responses; transient retries re-execute the original call and fallback guidance remains an error.
- Phase prevention rules are emitted from the v2 gateway, and their guidance is returned through the typed warning contract.
- Prompt-intelligence and workflow flight-recorder persistence now withhold raw prompts by default.
- `elite_memory` now supports explicit permanent deletion with `action="forget"`, and non-persisted workflow plans declare that `elite_progress` cannot resume them.
- Gateway argument schemas now constrain action enums, input sizes, and trust-score bounds for more reliable client-side tool selection.
- Runtime dependencies now use tested major-version bounds, and the release gate validates lock integrity, a high-severity Bandit scan, and an isolated installed-wheel CLI invocation.
- Source distributions now use an explicit allowlist and the release gate rejects local profiles, generated UI output, databases, environment files, and credential-like artifacts.
- Added a checksum-verified, redacted Gitleaks CI scan for both full Git history and the checked-out repository, with a narrow synthetic-fixture allowlist.
- Telemetry defaults to metadata-only retention; `off` disables usage logging, and raw retention requires explicit local opt-ins.
- User profile configuration is owner-only, migrates persisted provider/sync secrets out of JSON, and disables automatic boot sync.
- Team sync now requires `confirm=true`, approved host configuration, redirect blocking, explicit external/outbound grants, and quarantines imported records pending review.
- Release checks now validate the v2 protocol identity and compact contract instead of the obsolete 90-tool default.

### Security
- Removed plaintext API-key persistence from the user profile and moved credentials to process environment/keychain-backed configuration.
- Added common token, JSON secret, bearer-token, and private-key redaction before telemetry, error diagnostics, and outbound sync payloads.
- Prevented silent startup network writes and direct promotion of remotely supplied anti-patterns or decisions.
- Redact secret-like memory content, metadata, and workflow evidence before persistence; sensitive memory cannot be promoted and legacy v2 upgrades scrub covered raw prompts, telemetry, and stored records.
- Replaced MD5 context hashes with SHA-256, made the optional sync hub localhost-only by default, removed wildcard CORS, and require explicit custom-provider endpoint approval.

## [1.2.1] - 2026-07-10

### Added
- Security policy, support policy, code of conduct, governance notes, and citation metadata for public contribution readiness.
- Dependabot, CodeQL, dependency-review, and OpenSSF Scorecard workflows for supply-chain and repository security visibility.
- Discussion templates and stronger issue/PR templates with MCP runtime, privacy, and release-gate evidence fields.
- Elite telemetry, monitoring, and data-leverage roadmap for the next product-quality upgrade layer.

### Changed
- Improved README and package metadata for Model Context Protocol, AI IDE, coding-agent, workflow-memory, and evaluation-harness discoverability.
- Hardened GitHub Actions workflow permissions and concurrency defaults.
- Updated vulnerable dependencies in lockfiles: `starlette` 1.3.1, `pydantic-settings` 2.14.2, `langsmith` 0.9.7, `torch` 2.12.1, and telemetry UI PostCSS transitively via `next` 16.3.0-canary.77.
- Isolated package building, GitHub provenance attestation, and PyPI Trusted Publishing into separate least-privilege jobs.
- Pinned GitHub Actions and Docker build inputs to immutable digests and enabled Dependabot coverage for Docker.
- Replaced the legacy remote-bootstrap installer with an explicit `uv tool` installer that only changes IDE configuration when requested.

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
