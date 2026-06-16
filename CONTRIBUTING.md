# Contributing to Elite Reasoning MCP

Thank you for your interest in contributing! Here's how to get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/Snehgabani/elite-reasoning-mcp.git
cd elite-reasoning-mcp

# Install with dev dependencies
uv sync --extra dev

# Verify everything works
uv run pytest tests/ -v
uv run ruff check core/ tests/
```

## Making Changes

1. **Fork** the repository
2. **Create** a feature branch from `main`
3. **Make** your changes
4. **Run** the full CI pipeline locally before committing:
   ```bash
   uv run ruff check core/ tests/          # Lint
   uv run pytest tests/ -v --tb=short      # Tests
   uv build                                 # Build
   ```
5. **Commit** using [Conventional Commits](https://www.conventionalcommits.org/)
6. **Open** a Pull Request

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
│   └── tools/           # All 73 MCP tool implementations
├── tests/               # Pytest test suite
├── assets/              # Images and branding
└── pyproject.toml       # Project configuration
```

## Adding a New Tool

1. Add your tool function in the appropriate file under `core/tools/`
2. Register it with `@mcp.tool()` in `core/integration/mcp_server.py`
3. Add tests in `tests/`
4. Update the tool count in `README.md`

## Code Style

- We use **ruff** for linting
- Type hints are encouraged but not strictly enforced (pyright runs with `continue-on-error`)
- All new code should include docstrings

## Questions?

Open an [issue](https://github.com/Snehgabani/elite-reasoning-mcp/issues) — we're happy to help!
