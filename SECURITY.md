# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 2.0.x | Yes |
| < 2.0 | Upgrade first |

## Reporting a Vulnerability

Do not open a public issue for a vulnerability.

Report privately through GitHub Security Advisories:
https://github.com/Snehgabani/elite-reasoning-mcp/security/advisories/new

Please include:
- Affected version, commit, and installation method
- Minimal reproduction steps
- Expected impact and exploitability
- Whether persisted memory, local files, environment variables, or external API calls are involved
- Any safe proof-of-concept logs with secrets removed

Expected response targets:
- Initial acknowledgement: within 72 hours
- Triage decision: within 7 days when enough detail is provided
- Fix and disclosure timeline: based on severity and exploitability

## Security Model

Elite Reasoning MCP is designed to be local-first:
- Persistent memory is stored under `ELITE_BRAIN_DIR`.
- External model/API usage is opt-in through explicit environment configuration.
- Tool telemetry is metadata-only by default; raw telemetry and prompt storage require separate local opt-ins.
- Memory retrieval uses trust, confidence, scope, expiry, and privacy gates.
- Secret-like memory content and workflow evidence are redacted before persistence; sensitive memory stays quarantined and cannot be promoted into context.
- V2's one-time privacy migration replaces legacy raw prompts and telemetry summaries with metadata-only representations and scrubs redaction-covered legacy memory/workflow records.
- Quarantined or low-trust memories should not be injected into task context.
- Remote sync is legacy-only and requires confirmation, a host allowlist, network/outbound environment grants, and manual approval of imported records. Its optional hub binds to localhost by default; external binding requires credentials and an explicit environment grant. Multi-user hubs must use distinct credentials through `SYNC_USER_KEYS_JSON`; contributor identity is derived from the credential, not the request payload.
- Sync-hub LLM quality judging is disabled by default. It additionally requires `ELITE_SYNC_ENABLE_LLM_JUDGE=1`, rejects secret-like content before egress, and fails closed if the external judge is unavailable or returns an invalid verdict.
- Source distributions use an explicit allowlist, and the release gate rejects local profiles, team memory, databases, generated UI output, environment files, and credential-like artifacts.

Security-sensitive areas include:
- MCP tool registration and schema changes
- Memory search, context injection, quarantine, and sync behavior
- SQLite/FTS query construction
- Filesystem access and path handling
- Subprocess execution
- Network/API clients and configurable base URLs
- Dependency updates and GitHub Actions workflows

## Handling Secrets

Never include these in issues, discussions, logs, screenshots, eval fixtures, or tests:
- API keys or tokens
- Private source code
- Private prompts or proprietary requirements
- Raw persisted memory containing personal, customer, or production data
- Local filesystem paths that reveal sensitive organization details

If a secret is accidentally exposed, rotate it immediately before reporting.

## Dependency and Supply-Chain Policy

The repository uses:
- Dependabot for dependency update visibility
- CodeQL for static security scanning
- Dependency Review for pull requests
- OpenSSF Scorecard for public supply-chain posture
- Immutable SHA and digest pins for GitHub Actions and Docker build inputs
- GitHub artifact provenance attestations for release distributions
- Trusted Publishing and PyPI digital attestations through GitHub Actions OIDC
- A checksum-verified Gitleaks binary in a read-only workflow that scans Git history and checked-out files without printing secret values

New runtime dependencies should be justified in the PR with:
- Why the dependency is needed
- Maintenance and license posture
- Whether it handles secrets, network traffic, files, or untrusted input
- How failure modes are tested

## Repository Controls

The controls that require GitHub organization or repository settings are documented in [docs/repository-security.md](docs/repository-security.md). Maintainers should treat the checklist as a release prerequisite rather than assuming repository YAML alone enforces branch protection or GitHub-native secret scanning.
