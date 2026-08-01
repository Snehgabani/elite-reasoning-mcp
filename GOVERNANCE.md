# Governance

Elite Reasoning MCP is maintained by its project maintainers.

## Project Direction

The project prioritizes:
- Reliable Model Context Protocol behavior
- High-leverage workflows for AI coding agents and AI IDEs
- Local-first memory with trust, privacy, expiry, and scope controls
- Evidence-gated execution, release readiness, and eval scaffolding
- Security, maintainability, and clear contributor paths

## Contribution Decisions

Maintainers may accept changes when they:
- Solve a clear user problem
- Preserve or improve security and privacy posture
- Include tests or strong validation evidence
- Keep runtime dependencies justified
- Improve long-term maintainability

Maintainers may reject or defer changes when they:
- Increase hidden complexity without clear leverage
- Weaken memory safety, prompt-injection resilience, or release gates
- Add unmaintained dependencies or broad network/file access
- Duplicate existing capability without a migration plan

## Release Criteria

A release should pass:
- `uv run python scripts/release_check.py`
- GitHub Actions CI on supported Python versions
- Changelog update for user-visible changes
- Version update using semantic versioning
- Security review for dependency, memory, filesystem, network, subprocess, or MCP schema changes

## Maintainer Rights

Maintainers can make final decisions on scope, roadmap, releases, and moderation. The goal is to keep the project useful, secure, and easy to contribute to.
