"""Retrieve live pages and return verbatim quotes — not a research essay.

FEVER-style discipline (Thorne et al. 2018): a citation is valid only if the
quoted span actually occurs in fetched text. If retrieval is thin, we set
`degraded=True` and never invent URLs.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Sequence

MAX_QUOTES = 6
MAX_CHARS = 1200
MIN_QUOTE_WORDS = 8
MAX_QUOTE_WORDS = 40

SearchFn = Callable[[str, int], Awaitable[dict[str, Any]]]
ReadFn = Callable[[str, str], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class EvidenceQuote:
    url: str
    title: str
    quote: str
    published_date: str = ""
    provider: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GroundedEvidence:
    query: str
    quotes: tuple[EvidenceQuote, ...]
    sources_fetched: int
    sources_readable: int
    degraded: bool
    uncertain: tuple[str, ...]
    retrieved_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "quotes": [item.to_dict() for item in self.quotes],
            "sources_fetched": self.sources_fetched,
            "sources_readable": self.sources_readable,
            "degraded": self.degraded,
            "uncertain": list(self.uncertain),
            "retrieved_at": self.retrieved_at,
        }

    def compact_text(self) -> str:
        if not self.quotes:
            reason = "; ".join(self.uncertain) or "no readable sources"
            return f"No grounded quotes for `{self.query}`. {reason}. Do not invent citations."
        lines = [f"Grounded evidence for: {self.query}", f"Retrieved: {self.retrieved_at}"]
        if self.degraded:
            lines.append("DEGRADED: fewer than 2 quoted sources. Treat as incomplete.")
        for index, item in enumerate(self.quotes, 1):
            date = f" ({item.published_date})" if item.published_date else ""
            lines.append(f"[{index}] {item.url}{date}")
            lines.append(f'    "{item.quote}"')
        if self.uncertain:
            lines.append("UNCERTAIN: " + "; ".join(self.uncertain))
        return "\n".join(lines)


def _query_terms(query: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z0-9]{4,}", query)[:12]]


def _sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
    return [_clean_span(chunk) for chunk in chunks if _clean_span(chunk)]


def _clean_span(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _word_count(text: str) -> int:
    return len(text.split())


def extract_quotes(text: str, query: str, limit: int = 3) -> list[str]:
    """Pick verbatim spans that overlap the query and fit the quote budget."""
    terms = set(_query_terms(query))
    scored: list[tuple[int, str]] = []
    for sentence in _sentences(text):
        words = _word_count(sentence)
        if words < MIN_QUOTE_WORDS or words > MAX_QUOTE_WORDS:
            continue
        if sentence.lower() not in text.lower():
            continue
        overlap = sum(1 for term in terms if term in sentence.lower())
        if terms and overlap == 0:
            continue
        scored.append((overlap, sentence))
    scored.sort(key=lambda item: (-item[0], len(item[1])))
    unique: list[str] = []
    for _, sentence in scored:
        if sentence not in unique:
            unique.append(sentence)
        if len(unique) >= limit:
            break
    return unique


def _truncate_quotes(quotes: list[EvidenceQuote]) -> list[EvidenceQuote]:
    kept: list[EvidenceQuote] = []
    used = 0
    for item in quotes:
        cost = len(item.quote) + len(item.url)
        if used + cost > MAX_CHARS:
            break
        kept.append(item)
        used += cost
        if len(kept) >= MAX_QUOTES:
            break
    return kept


async def _default_search(query: str, k: int) -> dict[str, Any]:
    from core.evidence.web_research import LiveWebResearcher

    return await LiveWebResearcher(timeout=3.0, k=k).search_and_triangulate(query, k=k)


async def _default_read(url: str, query: str) -> dict[str, Any]:
    from core.evidence.deep_read import deep_read_url

    return await deep_read_url(url, query=query)


async def grounded_evidence(
    query: str,
    k: int = 3,
    *,
    search_fn: SearchFn | None = None,
    read_fn: ReadFn | None = None,
) -> GroundedEvidence:
    """Search, read, and return quotes. Fabrication is a bug, not a fallback."""
    cleaned = (query or "").strip()
    if not cleaned:
        raise ValueError("query is required")
    k = max(1, min(int(k), 5))
    search = search_fn or _default_search
    read = read_fn or _default_read
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        search_result = await search(cleaned, k)
    except Exception:
        search_result = {"sources": [], "degraded": True}

    sources: Sequence[dict[str, Any]] = search_result.get("sources") or []
    quotes: list[EvidenceQuote] = []
    readable = 0
    uncertain: list[str] = []

    for source in sources[:k]:
        url = str(source.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        try:
            page = await read(url, cleaned)
        except Exception:
            page = {"extracted": False, "url": url}
        if not page.get("extracted") or not str(page.get("text") or "").strip():
            uncertain.append(f"unreadable:{url}")
            continue
        readable += 1
        spans = extract_quotes(str(page.get("text") or ""), cleaned, limit=2)
        if not spans:
            uncertain.append(f"no_query_overlap:{url}")
            continue
        title = str(page.get("title") or source.get("title") or "")[:180]
        published = str(page.get("published_date") or "")
        provider = str(page.get("provider") or source.get("provider") or "")
        for span in spans:
            quotes.append(
                EvidenceQuote(
                    url=url,
                    title=title,
                    quote=span,
                    published_date=published,
                    provider=provider,
                )
            )

    quotes = _truncate_quotes(quotes)
    quoted_urls = {item.url for item in quotes}
    degraded = len(quoted_urls) < 2
    if degraded and "fewer than 2 quoted sources" not in uncertain:
        uncertain.append("fewer than 2 quoted sources")

    return GroundedEvidence(
        query=cleaned,
        quotes=tuple(quotes),
        sources_fetched=len(sources),
        sources_readable=readable,
        degraded=degraded,
        uncertain=tuple(dict.fromkeys(uncertain))[:8],
        retrieved_at=retrieved_at,
    )


def grounding_check(draft: str, evidence: GroundedEvidence) -> dict[str, Any]:
    """FEVER-style: URLs in the draft must appear in retrieved evidence; quotes must match."""
    urls = set(_URL_RE.findall(draft or ""))
    known = {item.url for item in evidence.quotes}
    known_quotes = {item.quote.lower() for item in evidence.quotes}
    hallucinated = sorted(url for url in urls if url not in known)
    used_quotes = [match[0] or match[1] for match in _QUOTE_RE.findall(draft or "")]
    unsupported_quotes = [span for span in used_quotes if span.lower() not in known_quotes]
    passed = not hallucinated and (not used_quotes or not unsupported_quotes)
    if urls and not known:
        passed = False
    return {
        "passed": passed,
        "cited_urls": sorted(urls),
        "known_urls": sorted(known),
        "hallucinated_urls": hallucinated,
        "unsupported_quotes": unsupported_quotes[:5],
        "degraded_evidence": evidence.degraded,
    }


_URL_RE = re.compile(r"https?://[^\s)>\]]+", re.I)
_QUOTE_RE = re.compile(r'"([^"]{12,240})"|“([^”]{12,240})”')
