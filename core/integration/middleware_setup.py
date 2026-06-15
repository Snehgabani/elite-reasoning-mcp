"""Middleware Setup — connects the MiddlewareChain to registered MCP tools.

This replaces the legacy _install_orchestration_interceptor monkey-patch
by wrapping each tool's function through the middleware chain.

Usage (in mcp_server.py):
    from core.integration.middleware_setup import wrap_registered_tools
    wrap_registered_tools(mcp, chain)
"""
import asyncio
import functools
import logging

from mcp.server.fastmcp import FastMCP

from core.middleware.chain import MiddlewareChain

logger = logging.getLogger(__name__)

# Tools that should NOT be wrapped (minimal overhead tools)
EXEMPT_TOOLS = frozenset({
    "get_user_profile",
    "update_user_config",
})


def _make_async_adapter(sync_fn):
    """Create an async wrapper for a sync function.
    
    Uses a factory pattern to avoid closure capture bugs when called in a loop.
    """
    @functools.wraps(sync_fn)
    async def _async_adapter(**kwargs):
        return sync_fn(**kwargs)
    return _async_adapter


def wrap_registered_tools(mcp: FastMCP, chain: MiddlewareChain) -> int:
    """Wrap all registered MCP tool functions through the middleware chain.
    
    This is the single point where middleware gets connected to tool execution.
    After this call, every tool invocation passes through the full chain:
      UsageLog → LatencyBudget → Prevention → Injection → PeriodicScan → Cost → Fallback → Retry
    
    Args:
        mcp: The FastMCP server instance with tools already registered.
        chain: The configured MiddlewareChain instance.
    
    Returns:
        Number of tools successfully wrapped.
    """
    if chain is None:
        logger.warning("middleware_setup: chain is None, skipping tool wrapping")
        return 0

    wrapped_count = 0
    try:
        tool_manager = mcp._tool_manager
        for tool_name, tool_obj in tool_manager._tools.items():
            if tool_name in EXEMPT_TOOLS:
                logger.debug(f"middleware_setup: skipping exempt tool {tool_name}")
                continue

            original_fn = tool_obj.fn
            
            # Don't double-wrap
            if getattr(original_fn, '_middleware_wrapped', False):
                logger.debug(f"middleware_setup: {tool_name} already wrapped, skipping")
                continue

            # chain.wrap() returns an async function that expects **kwargs
            # But MCP tools may be sync. We need to handle both cases.
            if asyncio.iscoroutinefunction(original_fn):
                wrapped_fn = chain.wrap(tool_name, original_fn)
            else:
                # Wrap sync function in async wrapper first
                # Use factory to avoid closure capture bug in loop
                async_fn = _make_async_adapter(original_fn)
                wrapped_fn = chain.wrap(tool_name, async_fn)

            # Mark as wrapped to prevent double-wrapping
            wrapped_fn._middleware_wrapped = True
            # Preserve error boundary flag if present
            if getattr(original_fn, '_has_error_boundary', False):
                wrapped_fn._has_error_boundary = True

            tool_obj.fn = wrapped_fn
            wrapped_count += 1

        logger.info("Middleware chain connected to tools",
                    extra={"wrapped": wrapped_count,
                           "exempt": len(EXEMPT_TOOLS),
                           "total": len(tool_manager._tools)})
    except Exception as e:
        logger.error("middleware_setup: failed to wrap tools",
                    extra={"error": str(e)}, exc_info=True)
        raise  # This is critical — don't silently fail

    return wrapped_count
