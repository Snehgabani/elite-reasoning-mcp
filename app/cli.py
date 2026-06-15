"""
Elite System — MCP Server Entry Point.

Boots the Elite Reasoning Framework as a lightweight MCP server.
No API keys. No LLM clients. No UI. Just data, memory, and reasoning frameworks.
"""
import argparse
import sys
import os

from core.integration.mcp_server import create_mcp_server


def main():
    parser = argparse.ArgumentParser(description="Elite Reasoning Framework — IDE Augmentation MCP Server")
    parser.add_argument(
        "--brain-dir",
        type=str,
        default=os.path.expanduser("~/.gemini/antigravity/scratch/elite-system/brain"),
        help="Path to the persistent brain directory (stores memory, decisions, anti-patterns)"
    )
    args = parser.parse_args()

    # Ensure brain directory exists
    os.makedirs(args.brain_dir, exist_ok=True)

    # Create and run the MCP server
    mcp = create_mcp_server(args.brain_dir)
    mcp.run()


if __name__ == "__main__":
    main()
