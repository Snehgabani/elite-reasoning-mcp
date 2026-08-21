"""
Multi-Hop Query Planner & Search Decomposer.
Transforms complex, ambiguous, or multi-faceted user research inquiries into
orthogonal, high-recall sub-queries optimized for web search engines.
Detects temporal anchors and prevents keyword drift.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


@dataclass(frozen=True)
class PlannedQuery:
    query_text: str
    focus_aspect: str
    is_temporal: bool = False
    temporal_anchor: str = ""


@dataclass(frozen=True)
class QueryPlan:
    original_inquiry: str
    sub_queries: tuple[PlannedQuery, ...]
    detected_temporal_year: Optional[int] = None
    stop_terms: tuple[str, ...] = field(default_factory=tuple)


class QueryPlanner:
    """
    Decomposes research topics into structured, non-overlapping search engine queries.
    """

    TEMPORAL_YEAR_RE = re.compile(r"\b(202[0-9]|19[0-9]{2})\b")
    FILLER_WORDS = {
        "please",
        "can",
        "you",
        "tell",
        "me",
        "what",
        "is",
        "the",
        "how",
        "to",
        "find",
        "search",
        "lookup",
        "give",
        "provide",
        "about",
        "regarding",
        "for",
        "with",
        "and",
        "in",
        "of",
        "a",
        "an",
        "on",
        "do",
        "does",
        "did",
        "why",
    }

    def __init__(self, current_year: Optional[int] = None):
        self.current_year = current_year or datetime.now(timezone.utc).year

    def clean_keywords(self, text: str) -> str:
        """Strips punctuation and conversational filler, preserving core entities."""
        tokens = re.findall(r"[A-Za-z0-9_-]+", text)
        meaningful = [t for t in tokens if t.lower() not in self.FILLER_WORDS]
        return " ".join(meaningful) if meaningful else text.strip()

    def plan(self, inquiry: str, max_hops: int = 3) -> QueryPlan:
        """
        Decomposes an inquiry into 1-3 targeted sub-queries.
        """
        clean_inquiry = inquiry.strip()
        if not clean_inquiry:
            return QueryPlan(original_inquiry="", sub_queries=())

        # Check temporal cues
        year_match = self.TEMPORAL_YEAR_RE.search(clean_inquiry)
        temporal_year = int(year_match.group(1)) if year_match else None
        is_recent = bool(re.search(r"\b(latest|recent|newest|current|today|status)\b", clean_inquiry, re.I))

        # Check if inquiry has explicit conjunctions (and, vs, compare, between)
        split_parts = re.split(r"\b(?:vs|versus|compare|and also|compared to|between)\b", clean_inquiry, flags=re.I)

        planned: List[PlannedQuery] = []

        if len(split_parts) >= 2:
            # Comparative / multi-faceted inquiry
            for idx, part in enumerate(split_parts[:max_hops]):
                kws = self.clean_keywords(part)
                aspect = f"Facet {idx + 1}"
                planned.append(
                    PlannedQuery(
                        query_text=kws,
                        focus_aspect=aspect,
                        is_temporal=is_recent or (temporal_year is not None),
                        temporal_anchor=str(temporal_year or self.current_year) if is_recent else "",
                    )
                )
        else:
            # Single inquiry: generate primary query + deep-dive aspect
            primary_kws = self.clean_keywords(clean_inquiry)
            planned.append(
                PlannedQuery(
                    query_text=primary_kws,
                    focus_aspect="Primary entity / concept",
                    is_temporal=is_recent or (temporal_year is not None),
                    temporal_anchor=str(temporal_year or self.current_year) if is_recent else "",
                )
            )

            # If multi-concept, add an evidence / benchmark / specification aspect
            if len(primary_kws.split()) >= 3 and max_hops >= 2:
                planned.append(
                    PlannedQuery(
                        query_text=f"{primary_kws} benchmark specification documentation",
                        focus_aspect="Technical specification and empirical data",
                        is_temporal=is_recent,
                        temporal_anchor=str(self.current_year) if is_recent else "",
                    )
                )

        return QueryPlan(
            original_inquiry=clean_inquiry,
            sub_queries=tuple(planned[:max_hops]),
            detected_temporal_year=temporal_year,
            stop_terms=tuple(self.FILLER_WORDS),
        )
