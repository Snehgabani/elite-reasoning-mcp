import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class MCPRegistry:
    """
    Reads an mcp_servers.json configuration and initializes MCP clients.
    """
    def __init__(self, brain_dir: str):
        self.config_path = Path(brain_dir) / "mcp_servers.json"
        self.tools: List[BaseTool] = []
        self._stacks = []

    async def initialize(self):
        """Asynchronously initialize all MCP server connections and load tools."""
        if not self.config_path.exists():
            logger.warning(f"MCP config not found at {self.config_path}")
            return

        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load MCP config: {e}")
            return

        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from langchain_mcp_adapters.tools import load_mcp_tools
        from contextlib import AsyncExitStack

        servers = config.get("mcpServers", {})
        
        async def init_server(name, server_config):
            try:
                command = server_config.get("command")
                args = server_config.get("args", [])
                env = server_config.get("env", None)
                
                logger.info(f"Initializing MCP server: {name}")
                server_params = StdioServerParameters(command=command, args=args, env=env)
                
                stack = AsyncExitStack()
                read, write = await stack.enter_async_context(stdio_client(server_params))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                
                server_tools = await load_mcp_tools(session)
                
                logger.info(f"Successfully loaded {len(server_tools)} tools from {name}")
                return stack, server_tools
            except Exception as e:
                logger.error(f"Failed to initialize MCP server {name}: {e}")
                return None, []

        tasks = [init_server(name, config) for name, config in servers.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Unhandled exception during MCP initialization: {result}")
                continue
            stack, server_tools = result
            if stack:
                self._stacks.append(stack)
            for t in server_tools:
                self.tools.append(t)

    def get_tools(self) -> List[BaseTool]:
        """Get all loaded MCP tools."""
        return self.tools
        
    async def cleanup(self):
        """Close all MCP sessions."""
        for stack in self._stacks:
            await stack.aclose()
        self._stacks.clear()
        self.tools.clear()
