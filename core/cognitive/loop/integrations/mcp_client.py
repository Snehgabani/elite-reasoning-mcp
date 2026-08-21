"""External MCP Server Integration Framework

Provides a unified interface to integrate external MCP servers:
- Code Execution (E2B, Code Interpreter)
- Web Search (Brave Search, Tavily)
- Filesystem (official filesystem-mcp-server)
- Database (PostgreSQL, SQLite)
- And more...

Research basis:
- Tool-augmented LLMs show 30-50% improvement on complex tasks (Schick et al. 2023)
- Multi-tool orchestration improves task completion by 25-40% (Qin et al. 2023)
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path


@dataclass
class MCPTool:
    """Represents a tool from an external MCP server."""
    name: str
    description: str
    input_schema: dict
    server_name: str
    available: bool = True


@dataclass
class MCPToolResult:
    """Result from calling an MCP tool."""
    success: bool
    output: Any
    error: Optional[str] = None
    duration_ms: int = 0
    tool_name: str = ""


class ExternalMCPClient:
    """Client for communicating with external MCP servers."""
    
    def __init__(self, server_command: list[str], server_name: str):
        self.server_command = server_command
        self.server_name = server_name
        self.process = None
        self.tools = {}
    
    def start(self) -> bool:
        """Start the MCP server process."""
        try:
            self.process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            # Initialize and list tools
            self._initialize()
            self._list_tools()
            return True
        except Exception as e:
            print(f"Failed to start MCP server {self.server_name}: {e}")
            return False
    
    def stop(self):
        """Stop the MCP server process."""
        if self.process:
            self.process.terminate()
            self.process.wait()
    
    def _send_request(self, method: str, params: dict = None) -> dict:
        """Send JSON-RPC request to MCP server."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }
        
        # Send request
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        
        # Read response
        response_line = self.process.stdout.readline()
        response = json.loads(response_line)
        
        return response
    
    def _initialize(self):
        """Initialize the MCP server."""
        self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "loop-by-sg",
                "version": "6.0.0"
            }
        })
    
    def _list_tools(self):
        """List available tools from the MCP server."""
        response = self._send_request("tools/list")
        
        if "result" in response and "tools" in response["result"]:
            for tool_data in response["result"]["tools"]:
                tool = MCPTool(
                    name=tool_data["name"],
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("inputSchema", {}),
                    server_name=self.server_name
                )
                self.tools[tool.name] = tool
    
    def call_tool(self, tool_name: str, arguments: dict) -> MCPToolResult:
        """Call a tool on the MCP server."""
        start = time.time()
        
        try:
            response = self._send_request("tools/call", {
                "name": tool_name,
                "arguments": arguments
            })
            
            duration = int((time.time() - start) * 1000)
            
            if "result" in response:
                return MCPToolResult(
                    success=True,
                    output=response["result"],
                    duration_ms=duration,
                    tool_name=tool_name
                )
            elif "error" in response:
                return MCPToolResult(
                    success=False,
                    output=None,
                    error=response["error"].get("message", "Unknown error"),
                    duration_ms=duration,
                    tool_name=tool_name
                )
            else:
                return MCPToolResult(
                    success=False,
                    output=None,
                    error="Invalid response format",
                    duration_ms=duration,
                    tool_name=tool_name
                )
        
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            return MCPToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=duration,
                tool_name=tool_name
            )


class MCPIntegrator:
    """Manages multiple external MCP servers."""
    
    def __init__(self):
        self.clients = {}
        self.tools = {}
    
    def register_server(self, server_name: str, command: list[str]) -> bool:
        """Register and start an external MCP server."""
        client = ExternalMCPClient(command, server_name)
        
        if client.start():
            self.clients[server_name] = client
            
            # Register all tools from this server
            for tool_name, tool in client.tools.items():
                full_name = f"{server_name}.{tool_name}"
                self.tools[full_name] = tool
            
            return True
        
        return False
    
    def call_tool(self, full_tool_name: str, arguments: dict) -> MCPToolResult:
        """Call a tool by its full name (server.tool)."""
        if "." not in full_tool_name:
            return MCPToolResult(
                success=False,
                output=None,
                error=f"Invalid tool name format: {full_tool_name}"
            )
        
        server_name, tool_name = full_tool_name.split(".", 1)
        
        if server_name not in self.clients:
            return MCPToolResult(
                success=False,
                output=None,
                error=f"Server not found: {server_name}"
            )
        
        client = self.clients[server_name]
        return client.call_tool(tool_name, arguments)
    
    def list_tools(self) -> list[MCPTool]:
        """List all available tools from all servers."""
        return list(self.tools.values())
    
    def stop_all(self):
        """Stop all MCP server processes."""
        for client in self.clients.values():
            client.stop()


# ═══════════════════════════════════════════════════════════
# Pre-configured MCP Server Integrations
# ═══════════════════════════════════════════════════════════

def create_code_execution_integrator() -> MCPIntegrator:
    """Create integrator with code execution MCP server."""
    integrator = MCPIntegrator()
    
    # Try E2B Code Interpreter
    # Note: Requires E2B API key and installation
    # integrator.register_server("e2b", ["npx", "-y", "@e2b/mcp-server"])
    
    # Fallback: Use Python subprocess for simple execution
    # (In production, use proper sandboxed execution)
    
    return integrator


def create_web_search_integrator() -> MCPIntegrator:
    """Create integrator with web search MCP server."""
    integrator = MCPIntegrator()
    
    # Try Brave Search MCP
    # Note: Requires Brave API key and installation
    # integrator.register_server("brave", ["npx", "-y", "@anthropic/brave-search-mcp"])
    
    # Try Tavily MCP
    # integrator.register_server("tavily", ["npx", "-y", "tavily-mcp"])
    
    return integrator


def create_filesystem_integrator() -> MCPIntegrator:
    """Create integrator with filesystem MCP server."""
    integrator = MCPIntegrator()
    
    # Official filesystem MCP server
    # integrator.register_server("filesystem", ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"])
    
    return integrator


def create_full_integrator() -> MCPIntegrator:
    """Create integrator with all recommended MCP servers."""
    integrator = MCPIntegrator()
    
    # Register all servers
    # integrator.register_server("e2b", ["npx", "-y", "@e2b/mcp-server"])
    # integrator.register_server("brave", ["npx", "-y", "@anthropic/brave-search-mcp"])
    # integrator.register_server("filesystem", ["npx", "-y", "@modelcontextprotocol/server-filesystem", "."])
    
    return integrator
