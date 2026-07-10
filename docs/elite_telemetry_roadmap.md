# Elite Telemetry, Monitoring, and Data-Leverage Roadmap

Elite Reasoning MCP already records tool usage, latency budgets, cost logs, workflow runs, quality scores, prevention rules, calibration predictions, and memory events. The next upgrade is to turn those raw signals into a privacy-first observability and improvement system.

## Non-Negotiable Principles

- Local-first by default: no hidden remote analytics or background uploads.
- Opt-in export only: users explicitly choose OpenTelemetry, Prometheus, file, or hosted sinks.
- Redaction before persistence: secrets, private code, raw prompts, and sensitive memory never leave the local trust boundary by default.
- Outcome-driven: measure task success, regression prevention, evidence quality, calibration, latency, and cost ROI, not vanity tool-call volume.
- User agency: every tracking mode must have clear configuration, retention, deletion, and export controls.

## Phase 1: Canonical Event Envelope

Add one normalized schema for all MCP activity:

| Field | Purpose |
|---|---|
| `event_id` | Stable UUID for dedupe and trace joins |
| `run_id` | Links tool calls to `workflow_run` |
| `session_id_hash` | Groups sessions without exposing identity |
| `project_hash` | Tracks project-level drift without leaking paths |
| `event_type` | `tool_call`, `memory_retrieval`, `decision`, `risk_gate`, `eval_result`, `error`, `feedback` |
| `tool_name` | MCP tool or resource name |
| `latency_ms` | Performance and ROI measurement |
| `status` | `success`, `failure`, `blocked`, `quarantined`, `skipped` |
| `confidence` | Model or agent confidence before result |
| `outcome_label` | Later user/test/judge outcome |
| `risk_level` | Security, privacy, destructive, production, or data-risk tier |
| `redaction_level` | `none`, `metadata_only`, `summary_only`, `quarantined` |
| `evidence_refs` | Test IDs, PR links, release-gate output hashes, eval result IDs |

Implementation path:
- Add `telemetry_events` table with schema versioning.
- Add a small `TelemetryEvent` Pydantic model.
- Update middleware to emit events through one writer.
- Backfill existing `tool_usage_log` into the event view without losing compatibility.

## Phase 2: Monitoring Exports

Expose signals without forcing a vendor:

- OpenTelemetry OTLP traces for tool calls, workflow steps, memory retrieval, and eval runs.
- Prometheus `/metrics` endpoint for local dashboards.
- JSONL export for offline analysis.
- SQLite views for local telemetry UI.
- Redacted bundle export for bug reports.

Core metrics:
- `elite_tool_call_total`
- `elite_tool_latency_ms`
- `elite_workflow_completion_ratio`
- `elite_memory_quarantine_total`
- `elite_memory_injection_total`
- `elite_prevention_rule_fire_total`
- `elite_prevention_rule_precision`
- `elite_eval_task_success`
- `elite_confidence_brier_score`
- `elite_release_gate_pass_total`
- `elite_security_block_total`

## Phase 3: Alerts and Health SLOs

Add local alert rules:

- P95 tool latency exceeds budget.
- Memory quarantine rate spikes.
- Prevention rules fire often but have low precision.
- Confidence is high while outcome labels are poor.
- Release doctor reports fewer exposed tools than expected.
- Eval task success regresses against the previous baseline.
- Security-sensitive tool calls lack validation evidence.

Implementation path:
- Add `monitoring_rules` table.
- Add `monitoring_status` MCP resource.
- Add `monitoring_check` tool that returns pass/warn/fail with evidence.
- Feed failures into `workflow_run` gates and `elite_doctor_json`.

## Phase 4: Feedback and Outcome Labeling

Add explicit outcome capture:

- `record_task_outcome(run_id, outcome, evidence, confidence_after)`
- `record_user_feedback(run_id, rating, reason, suggested_fix)`
- `label_tool_call(event_id, useful, unnecessary, harmful, reason)`
- `resolve_memory_impact(memory_id, helped, harmed, stale, sensitive)`

Why it matters:
- Turns telemetry into learning data.
- Retires noisy rules.
- Promotes memories that repeatedly help.
- Detects overconfident failure patterns.
- Creates benchmark datasets from real workflows with consent.

## Phase 5: Eval Flywheel

Build a continuous quality loop:

1. Convert real workflow failures into anonymized eval cases.
2. Run MCP-on vs MCP-off comparisons.
3. Track task success, regression prevention, evidence quality, calibration, latency, and cost ROI.
4. Promote rules/memories/tools only when outcome lift beats overhead.
5. Publish aggregate benchmark reports without private data.

Implementation path:
- Extend `export_eval_harness` with dataset snapshots.
- Add `eval_run` and `eval_compare` tools.
- Store baseline results in SQLite.
- Add release gate: block release when key eval suites regress.

## Phase 6: Security Telemetry

Track high-risk behavior locally:

- Prompt-injection attempts.
- Memory-poisoning attempts.
- Secret-like strings detected before persistence/export.
- Filesystem, subprocess, network, and SQL risk events.
- Policy bypass attempts.
- Unexpected tool fan-out or loop behavior.

Implementation path:
- Add security event taxonomy.
- Add redaction tests for every telemetry sink.
- Add `security_audit_pack` export with metadata-only evidence.
- Add alert rules for repeated suspicious patterns.

## Phase 7: Team and Maintainer Leverage

Add optional team workflows:

- Encrypted shared memory packs.
- Per-project telemetry profiles.
- Contributor quality dashboards.
- Release readiness timeline.
- Dependabot/security alert trend dashboard.
- Public anonymized benchmark leaderboard for example tasks.

Privacy requirement:
- Team sync must use explicit scopes, encryption, provenance, revocation, and retention controls.

## Highest-Leverage Next Builds

1. `telemetry_events` canonical schema and writer.
2. `monitoring_check` MCP tool plus `elite://monitoring` resource.
3. Local Prometheus metrics endpoint.
4. OTLP trace export behind `ELITE_TELEMETRY_OTLP_ENDPOINT`.
5. Redaction test suite for telemetry payloads.
6. Outcome-labeling tools tied to `workflow_run`.
7. Eval comparison snapshots from real workflows.
8. Telemetry UI pages for latency, tool usefulness, memory quality, and release readiness.
9. Security event taxonomy and alert rules.
10. Public sample dashboard using synthetic data for growth and trust.

## What Not To Build

- Hidden analytics.
- Raw prompt upload by default.
- Tool-call volume leaderboards that reward waste.
- Remote memory sync without encryption and scope controls.
- Monitoring that cannot explain which evidence caused an alert.
- Auto-generated rules that cannot be retired by measured false-positive rates.
