# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 1.2.x | Yes |
| < 1.2 | Upgrade first |

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
- Memory retrieval uses trust, confidence, scope, expiry, and privacy gates.
- Quarantined or low-trust memories should not be injected into task context.

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

New runtime dependencies should be justified in the PR with:
- Why the dependency is needed
- Maintenance and license posture
- Whether it handles secrets, network traffic, files, or untrusted input
- How failure modes are tested
