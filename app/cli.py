"""Backward-compatible CLI entry point for Elite Reasoning MCP."""

from core.integration.mcp_server import main as mcp_main


def main() -> int:
    """Delegate to the supported CLI so all entry points behave identically."""
    return mcp_main()


if __name__ == "__main__":
    raise SystemExit(main())
