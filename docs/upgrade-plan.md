# v2.0.1 Hardening and Upgrade Plan

## Shipped in this change

- Remove developer-machine paths and personal package metadata from runtime configuration.
- Default identities to `local-user`; use `ELITE_USER_ID` only for an explicit pseudonym.
- Stop profile, resource, log, orchestration, and LLM output from disclosing local identity, paths, or sync endpoints.
- Normalize `ELITE_BRAIN_DIR` and CLI `--brain-dir`, including `~` expansion.
- Require `confirm=true` before quarantined memory can be promoted.
- Make the telemetry UI use the configured local brain instead of a developer-specific path.
- Make Docker Compose runnable: override the MCP stdio entrypoint for Uvicorn, authenticate its health check, bind the published port to localhost, and build from `uv.lock`.

## Next: Evidence Integrity

The current workflow records evidence text but does not independently verify a command, artifact, or test result. Add a versioned evidence adapter contract with:

- Allowlisted local command execution and captured exit status, duration, and redacted output digest.
- Artifact assertions for files, test reports, and build metadata.
- Explicit `verified`, `failed`, and `unavailable` states; never represent unavailable validation as passing.
- A policy that requires independently verified evidence for terminal release steps.

Acceptance criteria: a workflow cannot be marked release-ready when a required evidence adapter failed, was skipped, or has no immutable result record.

## Next: Observability Without Surveillance

Keep monitoring local-first and aggregate-only:

- Emit counters and latency histograms for tool calls, validation outcomes, middleware blocks, memory quarantine, and sync failures.
- Store prompt and identity-free digests by default; retain raw prompts only behind existing explicit opt-ins.
- Add an exportable, redacted support bundle with a clear retention window and a user-triggered delete action.
- Add a health contract that distinguishes persistence, embeddings, optional integrations, and evidence-adapter availability.

Acceptance criteria: diagnostics reveal operational state without exposing prompt content, account names, file paths, credentials, or sync endpoints.

## Next: Product and Compatibility Cleanup

- Split the legacy tool catalog from the core gateway package and mark legacy network and monkey-patch behavior as compatibility-only.
- Replace broad exception swallowing in persistence and workflow helper paths with typed, user-visible degraded states.
- Add client compatibility tests for Codex, Claude Desktop, Cursor, VS Code, and raw MCP stdio.
- Add isolated wheel and container end-to-end tests to CI, including the Compose sync-server health check.

Acceptance criteria: the default five-tool core surface is independently tested from the legacy surface, and every supported installation route exercises a real MCP client.

## Release Gate

Before release, require the full Python release gate, telemetry UI build, Docker Compose configuration validation with a non-secret test key, a real stdio MCP client session, a source-distribution privacy scan, and green dependency/security scans. Legal ownership notices remain intentionally separate from runtime telemetry and configuration; change those only with an explicit licensing decision.
