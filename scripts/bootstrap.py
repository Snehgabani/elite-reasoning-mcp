import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def bootstrap(brain_dir: str):
    """
    Initializes the base directory structure and defaults for an Elite System.
    Run this when spinning up a fresh brain.
    """
    logger.info(f"Bootstrapping brain directory at {brain_dir}")
    
    brain_path = Path(brain_dir)
    brain_path.mkdir(parents=True, exist_ok=True)
    
    # 1. Setup Quarantine directory
    quarantine_path = brain_path / "skills" / ".quarantine"
    quarantine_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Ensured quarantine directory at {quarantine_path}")
    
    # 2. Setup default MCP servers
    mcp_config_path = brain_path / "mcp_servers.json"
    if not mcp_config_path.exists():
        logger.info("Generating default mcp_servers.json payload")
        
        default_mcp_payload = {
            "mcpServers": {
                "fetch": {
                    "command": "uvx",
                    "args": ["mcp-server-fetch"]
                },
                "github": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"]
                },
                "memory": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-memory"]
                },
                "sequential-thinking": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
                },
                "brave-search": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-brave-search"]
                },
                "puppeteer": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-puppeteer"]
                }
            }
        }
        
        mcp_config_path.write_text(json.dumps(default_mcp_payload, indent=2))
    else:
        logger.info("mcp_servers.json already exists. Skipping.")
        
if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Bootstrap Elite Reasoning System")
    parser.add_argument("--brain-dir", default="brain", help="Path to the brain directory")
    args = parser.parse_args()
    
    bootstrap(args.brain_dir)
