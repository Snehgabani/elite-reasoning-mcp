# Contributing to Elite Reasoning MCP

Elite Reasoning MCP is a Model Context Protocol server for AI coding agents. Contributions should improve reliability, reasoning quality, workflow evidence, security, or developer adoption without weakening the local-first privacy model.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/Snehgabani/elite-reasoning-mcp.git
cd elite-reasoning-mcp

# Install with dev dependencies
uv sync --extra dev

# Verify everything works
uv run python scripts/release_check.py
```

## Making Changes

1. **Fork** the repository
2. **Create** a feature branch from `main`
3. **Make** your changes
4. **Run** the full CI pipeline locally before committing:
   ```bash
   uv run python scripts/release_check.py
   ```
5. **Commit** using [Conventional Commits](https://www.conventionalcommits.org/)
6. **Open** a Pull Request

## Pull Request Quality Bar

Every non-trivial PR should include:
- Problem statement and user impact
- MCP tool/resource behavior changes
- Memory, privacy, or security impact
- Release-gate output from `uv run python scripts/release_check.py`
- Screenshots or CLI output when changing docs, UX, telemetry, or installation behavior
- Tests for new behavior, regressions, and security-sensitive edge cases

## Commit Convention

| Prefix | Use |
|--------|-----|
| `feat:` | New features |
| `fix:` | Bug fixes |
| `chore:` | Maintenance, dependencies |
| `docs:` | Documentation only |
| `test:` | Adding or fixing tests |
| `refactor:` | Code changes that don't fix a bug or add a feature |

## Project Structure

```
elite-reasoning-mcp/
├── core/
│   ├── integration/     # MCP server + middleware setup
│   ├── memory/          # Persistent store, graph, hybrid search
│   ├── middleware/       # 8-layer middleware chain
│   ├── learning/        # Self-improving modules
│   ├── scheduler/       # Optimization loop
│   └── tools/           # MCP tool implementations
├── tests/               # Pytest test suite
├── assets/              # Images and branding
└── pyproject.toml       # Project configuration
```

## Adding a New Tool

1. Add your tool function in the appropriate file under `core/tools/`
2. Prefer extending a typed `elite_*` action in `core/tools/gateway.py`; the default public surface is intentionally limited to five tools.
3. Add a legacy-only tool only when compatibility requires it, and document why it cannot be represented by the gateway contract.
4. Add protocol, privacy, and regression tests in `tests/`.
5. Update README/tool docs and release-doctor expectations if the exposed surface changes.
6. Confirm `elite_verify(check="doctor")` and `scripts/release_check.py` still pass.

## Code Style

- We use **ruff** for linting
- The v2 runtime/privacy/tool-contract slice must remain clean under the focused pyright release gate.
- All new code should include docstrings
- Security-sensitive parsing, SQL, filesystem, subprocess, and network changes need explicit tests

## Questions?

Use [GitHub Discussions](https://github.com/Snehgabani/elite-reasoning-mcp/discussions) for questions and design ideas. Use [GitHub Security Advisories](https://github.com/Snehgabani/elite-reasoning-mcp/security/advisories/new) for vulnerabilities.
