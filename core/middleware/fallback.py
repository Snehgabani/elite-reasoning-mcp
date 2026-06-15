"""Retry & Fallback middleware.
ChatGPT §8: "No tool retries or fallbacks. A supervisor tool that,
upon an error or empty result, can try alternative tools."

Implements:
1. RetryMiddleware — retries transient errors with exponential backoff
2. FallbackMiddleware — tries alternative tool when primary fails
"""
import logging
import time

from core.middleware.base import CallContext, CallResult, Middleware

logger = logging.getLogger(__name__)

# Transient error signatures that warrant a retry
TRANSIENT_ERRORS = (
    "SQLITE_BUSY",
    "database is locked",
    "connection refused",
    "timeout",
    "rate limit",
    "429",
    "503",
    "temporary failure",
)


class RetryMiddleware(Middleware):
    """Retries tool calls on transient errors with exponential backoff.
    
    Default: 2 retries, 0.5s initial delay, 2x backoff.
    Only retries errors matching TRANSIENT_ERRORS signatures.
    """
    name = "retry"
    applies_to = "*"

    def __init__(self, max_retries: int = 2, initial_delay: float = 0.5, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor

    async def on_error(self, ctx: CallContext, error: Exception) -> CallResult | None:
        error_str = str(error).lower()
        is_transient = any(sig.lower() in error_str for sig in TRANSIENT_ERRORS)

        if not is_transient:
            logger.debug("RetryMiddleware: non-transient error, not retrying",
                        extra={"tool": ctx.tool_name, "error": error_str[:200]})
            return None  # Let error propagate

        attempt = ctx.metadata.get('_retry_attempt', 0)
        if attempt >= self.max_retries:
            logger.warning("RetryMiddleware: max retries exhausted",
                          extra={"tool": ctx.tool_name, "attempts": attempt})
            return None  # Let error propagate

        delay = self.initial_delay * (self.backoff_factor ** attempt)
        ctx.metadata['_retry_attempt'] = attempt + 1

        logger.info("RetryMiddleware: retrying after transient error",
                    extra={"tool": ctx.tool_name, "attempt": attempt + 1,
                           "delay_s": delay, "error": error_str[:100]})

        time.sleep(delay)

        # Return a result that signals "retry" to the chain
        return CallResult(
            tool_name=ctx.tool_name,
            output=None,
            latency_ms=0,
            augmentations=[f"⟳ Retry {attempt + 1}/{self.max_retries} after {delay:.1f}s delay"],
            metadata={'_retry': True, '_retry_attempt': attempt + 1},
        )


# ── Fallback Tool Registry ──────────────────────────────
# Maps tool names to their fallback alternatives.
# When a tool fails, the system can suggest trying the fallback.
FALLBACK_REGISTRY: dict[str, list[str]] = {
    # If vector search fails, fall back to FTS
    "check_anti_patterns": ["search_decisions"],
    "search_decisions": ["check_anti_patterns"],
    # If calibration fails, suggest assessment
    "calibration_predict": ["assess_confidence"],
    # If graph query fails, suggest keyword search
    "query_temporal_graph": ["search_decisions", "check_anti_patterns"],
}


class FallbackMiddleware(Middleware):
    """When a tool fails, suggests alternative tools from the fallback registry.
    
    Does NOT auto-execute fallbacks (that would be dangerous).
    Instead, adds a suggestion to the error result so the LLM can decide.
    """
    name = "fallback"
    applies_to = "*"

    def __init__(self, registry: dict[str, list[str]] = None):
        self.registry = registry or FALLBACK_REGISTRY

    async def on_error(self, ctx: CallContext, error: Exception) -> CallResult | None:
        fallbacks = self.registry.get(ctx.tool_name, [])
        if not fallbacks:
            return None

        logger.info("FallbackMiddleware: suggesting alternatives",
                    extra={"tool": ctx.tool_name, "fallbacks": fallbacks})

        suggestion = (
            f"⚠️ Tool `{ctx.tool_name}` failed: {str(error)[:200]}. "
            f"Consider trying: {', '.join(f'`{f}`' for f in fallbacks)}"
        )

        return CallResult(
            tool_name=ctx.tool_name,
            output=suggestion,
            latency_ms=(time.time() - ctx.started_at) * 1000,
            error=str(error),
            augmentations=[suggestion],
            metadata={'_fallback_suggested': True, '_fallbacks': fallbacks},
        )
