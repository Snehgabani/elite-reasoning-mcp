"""
Error Boundary Decorator for MCP Tools (Gap #6 fix + P0 security fix)

Wraps every @mcp.tool() function so that unhandled exceptions become
sanitized MCP-safe errors instead of crashing the entire server process or
being returned as false-success text.

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
import os
import uuid

from core.logging_config import get_logger
from core.privacy import safe_error_detail
from core.tools.errors import EliteToolError, is_transient_error

logger = get_logger(__name__)


def _sanitized_error(tool_name: str, error: Exception, is_async: bool = False) -> EliteToolError:
    """Produce a safe error result without leaking tracebacks or sensitive values."""
    error_id = uuid.uuid4().hex[:12]
    prefix = "Async t" if is_async else "T"
    logger.error(
        f"{prefix}ool error caught by boundary",
        extra={
            "tool": tool_name,
            "error": safe_error_detail(error),
            "error_id": error_id,
        },
        # Full exception values can contain credentials or user content. Make
        # tracebacks an explicit local debugging opt-in.
        exc_info=os.environ.get("ELITE_DEBUG_ERRORS") == "1",
    )
    return EliteToolError(
        "tool_execution_failed",
        f"Tool `{tool_name}` failed safely (error id: {error_id}). Inspect local diagnostics for details.",
        retryable=is_transient_error(error),
    )


def safe_tool(func):
    """
    Decorator that catches unhandled exceptions in an MCP tool function and
    raises a sanitized ``EliteToolError``. FastMCP converts it into a protocol
    response with ``isError=true`` while keeping the server process alive.

    This prevents a single bad query (e.g., malformed FTS5 input)
    from killing all 49+ tools in the MCP server process.

    SECURITY: diagnostic values are redacted by default.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except EliteToolError:
            raise
        except Exception as error:
            raise _sanitized_error(func.__name__, error) from None

    setattr(wrapper, "_has_error_boundary", True)
    return wrapper


def safe_tool_async(func):
    """Async version of safe_tool for async tool functions."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except EliteToolError:
            raise
        except Exception as error:
            raise _sanitized_error(func.__name__, error, is_async=True) from None

    setattr(wrapper, "_has_error_boundary", True)
    return wrapper


def smart_wrap(func):
    """Auto-detect sync/async and apply the correct error boundary."""
    if asyncio.iscoroutinefunction(func):
        return safe_tool_async(func)
    return safe_tool(func)
