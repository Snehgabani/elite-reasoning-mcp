import argparse
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def bootstrap(brain_dir: str, include_demo_mcps: bool = False):
    """
    Initializes the base directory structure and defaults for an Elite System.
    Run this when spinning up a fresh brain.
    """
    logger.info(f"Bootstrapping brain directory at {brain_dir}")

    brain_path = Path(brain_dir)
    brain_path.mkdir(parents=True, mode=0o700, exist_ok=True)
    try:
        os.chmod(brain_path, 0o700)
    except OSError as exc:
        logger.debug("Non-fatal chmod failed on %s: %s", brain_path, exc)

    # 1. Setup Quarantine directory
    quarantine_path = brain_path / "skills" / ".quarantine"
    quarantine_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Ensured quarantine directory at {quarantine_path}")

    # 2. Setup default MCP servers
    mcp_config_path = brain_path / "mcp_servers.json"
    if not mcp_config_path.exists():
        logger.info("Generating default mcp_servers.json payload")

        default_mcp_payload = {"mcpServers": {}}
        if include_demo_mcps:
            default_mcp_payload["mcpServers"] = {
                "fetch": {"command": "uvx", "args": ["mcp-server-fetch"]},
            }
            logger.warning("Demo MCP configuration enabled; review and pin every third-party tool before use.")
        mcp_config_path.write_text(json.dumps(default_mcp_payload, indent=2))
        try:
            os.chmod(mcp_config_path, 0o600)
        except OSError as exc:
            logger.debug("Non-fatal chmod failed on %s: %s", mcp_config_path, exc)
    else:
        logger.info("mcp_servers.json already exists. Skipping.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Bootstrap Elite Reasoning System")
    parser.add_argument("--brain-dir", default="brain", help="Path to the brain directory")
    parser.add_argument(
        "--include-demo-mcps",
        action="store_true",
        help="Add a single demo MCP entry; review and pin it before execution.",
    )
    args = parser.parse_args()

    bootstrap(args.brain_dir, include_demo_mcps=args.include_demo_mcps)
