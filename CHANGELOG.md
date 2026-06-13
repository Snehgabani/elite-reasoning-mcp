# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-06-13

### Added
- 66 reasoning tools across 7 categories
- `orchestrate_request_tool` — intent classification with 13 categories and complexity scoring
- Anti-pattern memory — stores mistakes with root cause and fix, checks before acting
- Decision council — 5 adversarial perspectives review every major decision
- FMEA risk analysis — failure mode analysis before building
- Confidence calibration — prediction tracking with Brier scores
- Cross-session memory via local SQLite (15 tables, 32 indexes)
- Knowledge graph store for entity-relationship tracking
- Optional semantic search via `sqlite-vec` and `sentence-transformers`
- Custom prevention rules — auto-triggered safeguards
- Five Whys root cause analysis
- After Action Review for post-mortem learning
- Socratic challenge for stress-testing reasoning
- Autonomous scan and self-diagnosis
- One-click installers for macOS/Linux (`scripts/install.sh`) and Windows (`scripts/install.ps1`)
- Docker support via `Dockerfile`
- CI/CD via GitHub Actions (9-platform test matrix + lint + Docker)
- IDE support for Cursor, Claude Desktop, VS Code, Windsurf, Antigravity
- Full documentation in `docs/TOOLS.md` and `docs/ARCHITECTURE.md`

[1.0.0]: https://github.com/Snehgabani/elite-reasoning-mcp/releases/tag/v1.0.0
