import pytest
import asyncio
import json
from pathlib import Path
from core.skills.mcp_registry import MCPRegistry

@pytest.mark.asyncio
async def test_mcp_registry_empty(tmp_path):
    # Without mcp_servers.json, it should gracefully initialize with no tools.
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    
    registry = MCPRegistry(str(brain_dir))
    await registry.initialize()
    
    tools = registry.get_tools()
    assert len(tools) == 0
    await registry.cleanup()

@pytest.mark.asyncio
async def test_mcp_registry_with_config(tmp_path):
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    
    # Write a dummy config for mcp-server-fetch.
    # Note: If `uvx mcp-server-fetch` is not installed or too slow, we can just test that the config parses
    # and tries to run. But we might get an error. Let's provide a non-existent command to see if it handles errors gracefully.
    config = {
        "mcpServers": {
            "fetch": {
                "command": "nonexistent-command-for-test",
                "args": []
            }
        }
    }
    
    config_file = brain_dir / "mcp_servers.json"
    config_file.write_text(json.dumps(config))
    
    registry = MCPRegistry(str(brain_dir))
    await registry.initialize()
    
    tools = registry.get_tools()
    assert len(tools) == 0  # It should fail gracefully
    await registry.cleanup()
