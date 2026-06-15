"""Base middleware classes for the Elite Reasoning MCP.
Replaces the monkey-patched _intercepted_call_tool with explicit,
testable, composable middleware."""
from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CallContext:
    """Context passed through the middleware chain for each tool call."""
    tool_name: str
    args: dict
    session_id: str
    started_at: float
    metadata: dict = field(default_factory=dict)


@dataclass
class CallResult:
    """Result container that middleware can modify."""
    value: Any
    duration_ms: float = 0.0
    short_circuited: bool = False
    augmentations: list[str] = field(default_factory=list)


class Middleware(ABC):
    """Base middleware class. Each middleware decides per-tool whether it applies."""
    name: str = "unnamed"
    applies_to: set[str] | str = "*"  # "*" = all tools, or set of tool names

    def matches(self, tool_name: str) -> bool:
        return self.applies_to == "*" or tool_name in self.applies_to

    async def before(self, ctx: CallContext) -> Optional[CallResult]:
        """Return CallResult to short-circuit. Return None to continue."""
        return None

    async def after(self, ctx: CallContext, result: CallResult) -> CallResult:
        """Modify or augment the result. Called in reverse order."""
        return result

    async def on_error(self, ctx: CallContext, exc: Exception) -> Optional[CallResult]:
        """Return CallResult to suppress error. Return None to re-raise."""
        return None
