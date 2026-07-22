"""Retry & Fallback middleware.
ChatGPT §8: "No tool retries or fallbacks. A supervisor tool that,
upon an error or empty result, can try alternative tools."

Implements:
1. RetryMiddleware — retries transient errors with exponential backoff
2. FallbackMiddleware — tries alternative tool when primary fails
"""
import logging
from typing import Optional

from core.middleware.base import CallContext, CallResult, Middleware
from core.tools.errors import EliteToolError, is_transient_error

logger = logging.getLogger(__name__)

class RetryMiddleware(Middleware):
    """Retries tool calls on transient errors with exponential backoff.
    
    Default: 2 retries, 0.5s initial delay, 2x backoff.
    Only retries transient errors. The chain owns re-execution so a retry is a
    real second call, not a successful placeholder response.
    """
    name = "retry"
    applies_to = "*"

    def __init__(self, max_retries: int = 2, initial_delay: float = 0.5, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Return whether the chain should execute the original call again."""
        if attempt >= self.max_retries:
            return False
        if isinstance(error, EliteToolError):
            return error.retryable
        return is_transient_error(error)

    def delay_for(self, attempt: int) -> float:
        """Calculate exponential backoff for the next retry attempt."""
        return self.initial_delay * (self.backoff_factor ** attempt)

    async def on_error(self, ctx: CallContext, exc: Exception) -> CallResult | None:
        """Retry execution is owned by ``MiddlewareChain``."""
        return None


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

    def __init__(self, registry: Optional[dict[str, list[str]]] = None):
        self.registry = registry if registry is not None else FALLBACK_REGISTRY

    def fallbacks_for(self, tool_name: str) -> tuple[str, ...]:
        """Return safe alternatives without converting a failure into success."""
        return tuple(self.registry.get(tool_name, []))

    async def on_error(self, ctx: CallContext, exc: Exception) -> CallResult | None:
        return None
