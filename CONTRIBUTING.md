# Contributing to Elite Reasoning MCP

Thank you for your interest in contributing! This guide will help you get started.

## 🚀 Quick Start

```bash
# 1. Fork & clone
git clone https://github.com/YOUR_USERNAME/elite-reasoning-mcp.git
cd elite-reasoning-mcp

# 2. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Install dependencies
uv sync --dev

# 4. Run the server locally
uv run python -c "from core.integration.mcp_server import create_mcp_server; server = create_mcp_server('./brain'); server.run()"
```

## 🏗️ Project Structure

```
core/
├── integration/
│   └── mcp_server.py          # FastMCP server — ALL tools registered here
├── tools/
│   ├── orchestration.py        # orchestrate_request_tool (the core pipeline)
│   ├── reasoning_amplifier.py  # Calibration, Decision Council, Preflight
│   ├── adaptive.py             # User modeling, learning, prompt tracking
│   ├── analysis.py             # Risk, FMEA, Bayesian, EV calculations
│   ├── auditing.py             # Quality scoring, anti-patterns, bias scan
│   ├── planning.py             # Goals, benchmarks, workflow
│   ├── native_tools.py         # Memory search, sync, context
│   ├── graph_tools.py          # Knowledge graph, temporal queries
│   └── error_boundary.py       # Error handling wrapper
├── memory/
│   ├── persistent_store.py     # SQLite database (15 tables, 32 indexes)
│   ├── graph_store.py          # Knowledge graph store
│   └── embedding.py            # Optional semantic search
└── identity/
    └── user_profile.py         # Per-user configuration
```

## 🔧 Adding a New Tool

1. **Choose the right file** — Pick the tool file that matches your tool's category
2. **Write the tool function** — Use the `@mcp.tool()` decorator:

```python
@mcp.tool()
def my_new_tool(param1: str, param2: int = 10) -> str:
    """One-line description of what this tool does.

    Args:
        param1: Description of param1.
        param2: Description of param2. Defaults to 10.
    """
    # Your implementation
    return "Result"
```

3. **Register it** — Add a call to your tool's `register(mcp, store)` in `mcp_server.py`
4. **Test it** — Run the server and verify the tool appears:

```bash
uv run python -c "
from core.integration.mcp_server import create_mcp_server
server = create_mcp_server('./test_brain')
print(f'Tools: {len(server._tool_manager._tools)}')
"
```

5. **Create a schema** — Add a JSON schema in `schemas/your_tool_name.json`

## 📋 PR Guidelines

- **One tool per PR** when adding new tools
- **Include tests** or a verification script
- **Update README** if adding a new category
- **Add schema** in `schemas/` directory
- **Keep it local** — no external API calls without discussion

## 🧪 Testing

```bash
# Import test
uv run python -c "from core.integration.mcp_server import create_mcp_server; print('OK')"

# Server creation test
uv run python -c "
from core.integration.mcp_server import create_mcp_server
import tempfile
server = create_mcp_server(tempfile.mkdtemp())
print(f'✅ {len(server._tool_manager._tools)} tools loaded')
"
```

## 💡 Contribution Ideas

- [ ] Add **Dockerfile** for containerized deployment
- [ ] Add **benchmarks** comparing output quality with/without pipeline
- [ ] Improve **intent classifier** accuracy
- [ ] Add **more IDE installers** (Windsurf, Zed, etc.)
- [ ] Write **integration tests** for each tool
- [ ] Add **i18n support** for tool descriptions
- [ ] Create **VS Code extension** for visual tool management

## 📝 Code Style

- Python 3.11+ features are welcome
- Use type hints
- Docstrings on all public functions
- Keep tool functions focused — one tool, one job
- UTC timestamps everywhere (`time.gmtime()`)

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.
