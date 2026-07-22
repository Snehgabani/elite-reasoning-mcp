"""Typed, sanitized failures for MCP tool execution."""

from __future__ import annotations

TRANSIENT_ERROR_MARKERS = (
    "sqlite_busy",
    "database is locked",
    "connection refused",
    "timeout",
    "rate limit",
    "429",
    "503",
    "temporary failure",
)


def is_transient_error(error: Exception | str) -> bool:
    message = str(error).lower()
    return any(marker in message for marker in TRANSIENT_ERROR_MARKERS)


class EliteToolError(Exception):
    """An MCP-safe error that preserves retry and fallback metadata internally."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        fallback_tools: tuple[str, ...] = (),
    ) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        self.fallback_tools = fallback_tools
        super().__init__(f"[{code}] {message}")

    def with_fallbacks(self, fallback_tools: tuple[str, ...]) -> "EliteToolError":
        if not fallback_tools:
            return self
        suggestion = f" Try: {', '.join(fallback_tools)}."
        return EliteToolError(
            self.code,
            self.message + suggestion,
            retryable=self.retryable,
            fallback_tools=fallback_tools,
        )


def validation_error(message: str) -> EliteToolError:
    """Return a predictable validation failure for invalid tool arguments."""
    return EliteToolError("validation_error", message)
