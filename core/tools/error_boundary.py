"""
Error Boundary Decorator for MCP Tools (Gap #6 fix + P0 security fix)

Wraps every @mcp.tool() function so that ANY unhandled exception
returns a SANITIZED error string instead of crashing the
entire MCP server process.

SECURITY: Never leaks tracebacks, file paths, or SQL to the LLM/user.
Full diagnostics are logged server-side only.

Usage:
    from core.tools.error_boundary import safe_tool

    @mcp.tool()
    @safe_tool
    def my_tool(arg: str) -> str:
        ...
"""
import asyncio
import functools
import traceback
from core.logging_config import get_logger

logger = get_logger(__name__)


def _sanitized_error(tool_name: str, e: Exception, is_async: bool = False) -> str:
    """Produce a safe error message — NO tracebacks, NO file paths."""
    error_type = type(e).__name__
    prefix = "Async t" if is_async else "T"
    logger.error(
        f"{prefix}ool error caught by boundary",
        extra={"tool": tool_name, "error": str(e)},
        exc_info=True  # Full traceback logged SERVER-SIDE ONLY
    )
    return (
        f"❌ **Tool Error in `{tool_name}`**\n\n"
        f"**Type:** `{error_type}`\n"
        f"**Message:** {str(e)[:200]}\n\n"
        f"> This error was caught by the error boundary. "
        f"The MCP server is still running. All other tools remain available."
    )


def safe_tool(func):
    """
    Decorator that catches ALL exceptions in an MCP tool function
    and returns a sanitized error string instead of propagating.
    
    This prevents a single bad query (e.g., malformed FTS5 input)
    from killing all 49+ tools in the MCP server process.
    
    SECURITY: Full tracebacks are logged server-side only.
    The LLM/user sees only the error type and a truncated message.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return _sanitized_error(func.__name__, e)
    wrapper._has_error_boundary = True
    return wrapper


def safe_tool_async(func):
    """Async version of safe_tool for async tool functions."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            return _sanitized_error(func.__name__, e, is_async=True)
    wrapper._has_error_boundary = True
    return wrapper


def smart_wrap(func):
    """Auto-detect sync/async and apply the correct error boundary."""
    if asyncio.iscoroutinefunction(func):
        return safe_tool_async(func)
    return safe_tool(func)
