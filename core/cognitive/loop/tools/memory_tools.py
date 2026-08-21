"""Memory Tool — Consolidated memory, anti-pattern, and decision management.

Single tool for all memory operations: search, remember, forget,
record anti-patterns, record decisions. Trust-gated and privacy-aware.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from core.cognitive.loop.core.store import SingularityStore

_MEMORY_ANNOTATIONS = ToolAnnotations(
    title="Manage trusted memory",
    readOnlyHint=False,
    destructiveHint=True,  # forget action permanently deletes
    idempotentHint=False,
    openWorldHint=False,
)


class MemoryResult(BaseModel):
    action: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    id: int | None = None
    stats: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def register(mcp, store: SingularityStore):
    """Register the memory tool."""

    @mcp.tool(name="memory", annotations=_MEMORY_ANNOTATIONS)
    def memory(
        action: str = "search",
        query: Annotated[str, Field(default="", max_length=2000)] = "",
        content: Annotated[str, Field(default="", max_length=5000)] = "",
        memory_type: Annotated[str, Field(default="fact", max_length=80)] = "fact",
        scope: Annotated[str, Field(default="global", max_length=128)] = "global",
        trust_score: Annotated[float, Field(default=0.7, ge=0.0, le=1.0)] = 0.7,
        root_cause: Annotated[str, Field(default="", max_length=2000)] = "",
        fix: Annotated[str, Field(default="", max_length=2000)] = "",
        rationale: Annotated[str, Field(default="", max_length=2000)] = "",
        alternatives: Annotated[str, Field(default="", max_length=2000)] = "",
        decision: Annotated[str, Field(default="", max_length=2000)] = "",
        context: Annotated[str, Field(default="", max_length=2000)] = "",
        expected_outcome: Annotated[str, Field(default="", max_length=2000)] = "",
        memory_id: Annotated[int, Field(default=0, ge=0)] = 0,
        confirm: bool = False,
    ) -> MemoryResult:
        """Store, search, or manage cross-session knowledge. Actions: search, remember, forget, mistake, decision, stats, list. Use 'mistake' to prevent repeating errors. Use 'decision' for audit trail. Skip for stateless tasks.

        Trust-gated: low-trust items deprioritized. Privacy-gated: secret items require trust ≥ 0.9.
        """
        act = action.strip().lower()

        # Parameter normalization & fallback aliasing
        effective_content = content.strip() or decision.strip()
        effective_rationale = rationale.strip() or context.strip()
        effective_alternatives = alternatives.strip() or expected_outcome.strip()

        if act in ("search", "find", "query"):
            search_query = query.strip() or effective_content
            if not search_query:
                return MemoryResult(action="search", warnings=["Query is empty."])
            items = store.search_memory(search_query, scope=scope, limit=10, min_trust=0.3)
            return MemoryResult(
                action="search",
                items=[
                    {"id": m["id"], "type": m["memory_type"], "content": m["content"][:500], "trust": m["trust_score"]}
                    for m in items
                ],
                warnings=[f"Found {len(items)} items."] if items else ["No matches."],
            )

        elif act in ("list", "recent", "get"):
            items = (
                store.search_memory("", scope=scope, limit=15, min_trust=0.0) if hasattr(store, "search_memory") else []
            )
            stats = store.get_memory_stats()
            return MemoryResult(
                action="list",
                items=[
                    {"id": m["id"], "type": m["memory_type"], "content": m["content"][:300], "trust": m["trust_score"]}
                    for m in items
                ]
                if items
                else [],
                stats=stats,
                warnings=[f"Retrieved {len(items)} recent memory records."],
            )

        elif act in ("remember", "save", "store"):
            if not effective_content:
                return MemoryResult(action="remember", warnings=["Content required."])
            item_id = store.remember(memory_type, effective_content, scope, trust_score=trust_score)
            warnings = ["Low trust — deprioritized in search."] if trust_score < 0.5 else []
            return MemoryResult(action="remember", id=item_id, warnings=warnings)

        elif act in ("forget", "delete", "remove"):
            if memory_id < 1:
                return MemoryResult(action="forget", warnings=["memory_id required."])
            if not confirm:
                return MemoryResult(action="forget", warnings=["Set confirm=true to permanently delete."])
            deleted = store.forget_memory(memory_id)
            return MemoryResult(action="forget", warnings=["Deleted." if deleted else "Not found."])

        elif act in ("mistake", "anti_pattern", "error"):
            if not effective_content:
                effective_content = root_cause or fix or "Identified systemic anti-pattern"
            item_id = store.record_anti_pattern(effective_content, root_cause, fix, "medium", "")
            return MemoryResult(
                action="mistake", id=item_id, warnings=["Recorded. Will surface when similar tasks appear."]
            )

        elif act in ("decision", "record_decision"):
            if not effective_content:
                return MemoryResult(
                    action="decision", warnings=["Decision description required in 'content' or 'decision'."]
                )
            item_id = store.record_decision(effective_content, effective_rationale, effective_alternatives, "")
            return MemoryResult(action="decision", id=item_id, warnings=[f"Decision #{item_id} recorded."])

        elif act in ("stats", "summary", "count"):
            stats = store.get_memory_stats()
            return MemoryResult(action="stats", stats=stats)

        return MemoryResult(
            action=action,
            warnings=[f"Unknown action: {action}. Valid: search, remember, forget, mistake, decision, stats, list."],
        )
