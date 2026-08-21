"""Middleware chain that wraps tool functions with composable hooks."""

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

from core.middleware.base import CallContext, CallResult, Middleware
from core.middleware.fallback import FallbackMiddleware, RetryMiddleware
from core.tools.errors import EliteToolError, is_transient_error

logger = logging.getLogger(__name__)


def _render(ctx: CallContext, result: CallResult):
    """Prepend augmentations to the user-visible payload."""
    if not result.augmentations:
        return result.value
    prefix = "\n\n".join(result.augmentations)
    if isinstance(result.value, str):
        return prefix + "\n\n---\n\n" + result.value
    # The compact gateway declares a stable `warnings` field. Preserve the
    # schema while surfacing evidence/prevention feedback to the client.
    model_fields = getattr(type(result.value), "model_fields", {})
    if "warnings" in model_fields and hasattr(result.value, "model_copy"):
        return result.value.model_copy(update={"warnings": list(result.augmentations)})
    # Other structured results do not get ad-hoc wrapper keys because that
    # would silently violate their output schema contract.
    return result.value


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
            call_args = dict(kwargs)
            ctx = CallContext(
                tool_name=tool_name,
                args=call_args,
                session_id=call_args.pop("_session_id", "default"),
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

            # ── EXECUTE: retry transient failures against the original call ──
            retry_middleware = next((mw for mw in relevant if isinstance(mw, RetryMiddleware)), None)
            attempt = 0
            while True:
                try:
                    value = await fn(**call_args)
                    result = CallResult(
                        value=value,
                        duration_ms=(time.perf_counter() - ctx.started_at) * 1000,
                    )
                    if attempt:
                        ctx.metadata["retry_attempts"] = attempt
                    break
                except Exception as exc:
                    if retry_middleware is not None and retry_middleware.should_retry(exc, attempt):
                        delay = retry_middleware.delay_for(attempt)
                        attempt += 1
                        logger.info(
                            "RetryMiddleware: retrying transient tool failure",
                            extra={"tool": tool_name, "attempt": attempt, "delay_s": delay},
                        )
                        await asyncio.sleep(delay)
                        continue

                    failure = (
                        exc
                        if isinstance(exc, EliteToolError)
                        else EliteToolError(
                            "tool_execution_failed",
                            f"Tool `{tool_name}` failed safely. Inspect local diagnostics for details.",
                            retryable=is_transient_error(exc),
                        )
                    )
                    fallback_middleware = next((mw for mw in relevant if isinstance(mw, FallbackMiddleware)), None)
                    if fallback_middleware is not None:
                        failure = failure.with_fallbacks(fallback_middleware.fallbacks_for(tool_name))
                    raise failure from None

            # ── POST chain: reverse order, each can modify result ──
            for mw in reversed(relevant):
                try:
                    result = await mw.after(ctx, result)
                except Exception as e:
                    logger.warning(f"middleware.after {mw.name} failed: {e}")

            return _render(ctx, result)

        return wrapped
