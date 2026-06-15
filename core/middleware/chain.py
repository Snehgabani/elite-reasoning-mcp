"""Middleware chain that wraps tool functions with composable hooks."""
import time
import logging
from typing import Any, Callable, Awaitable
from core.middleware.base import Middleware, CallContext, CallResult

logger = logging.getLogger(__name__)


def _render(ctx: CallContext, result: CallResult):
    """Prepend augmentations to the user-visible payload."""
    if not result.augmentations:
        return result.value
    prefix = "\n\n".join(result.augmentations)
    if isinstance(result.value, str):
        return prefix + "\n\n---\n\n" + result.value
    if isinstance(result.value, dict):
        return {"_warnings": result.augmentations, "data": result.value}
    return {"_warnings": result.augmentations, "data": str(result.value)}


class MiddlewareChain:
    """Composable middleware chain for MCP tool execution.
    
    Usage:
        chain = MiddlewareChain()
        chain.use(PreventionRuleMiddleware(store))
        chain.use(AntiPatternInjectionMiddleware(store))
        chain.use(UsageLogMiddleware(store))
        
        wrapped_fn = chain.wrap("tool_name", original_fn)
    """
    
    def __init__(self):
        self._middlewares: list[Middleware] = []
    
    def use(self, mw: Middleware) -> "MiddlewareChain":
        """Add a middleware to the chain. Order matters."""
        self._middlewares.append(mw)
        return self
    
    def wrap(self, tool_name: str, fn: Callable[..., Awaitable[Any]]) -> Callable:
        """Returns a new async function with the chain applied."""
        relevant = [m for m in self._middlewares if m.matches(tool_name)]
        
        async def wrapped(**kwargs):
            ctx = CallContext(
                tool_name=tool_name,
                args=kwargs,
                session_id=kwargs.pop("_session_id", "default"),
                started_at=time.perf_counter(),
            )
            
            # ── PRE chain: first one to return a result short-circuits ──
            for mw in relevant:
                try:
                    early = await mw.before(ctx)
                except Exception as e:
                    logger.warning(f"middleware.before {mw.name} failed: {e}")
                    continue
                if early is not None:
                    early.short_circuited = True
                    return _render(ctx, early)
            
            # ── EXECUTE: run the original tool (timed) ──
            try:
                value = await fn(**kwargs)
                result = CallResult(
                    value=value,
                    duration_ms=(time.perf_counter() - ctx.started_at) * 1000,
                )
            except Exception as exc:
                # ── ERROR chain: each middleware can suppress ──
                for mw in relevant:
                    try:
                        suppressed = await mw.on_error(ctx, exc)
                    except Exception:
                        continue
                    if suppressed is not None:
                        return _render(ctx, suppressed)
                raise
            
            # ── POST chain: reverse order, each can modify result ──
            for mw in reversed(relevant):
                try:
                    result = await mw.after(ctx, result)
                except Exception as e:
                    logger.warning(f"middleware.after {mw.name} failed: {e}")
            
            return _render(ctx, result)
        
        return wrapped
