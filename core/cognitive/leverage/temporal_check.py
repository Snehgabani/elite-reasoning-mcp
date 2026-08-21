# src/leverage/temporal_check.py
# TEMPORAL VERIFICATION — date-aware freshness routing for claims.
#
# Extracts publication dates from source URLs (arXiv/YYYY/MM conventions).
# If no date can be established, the verdict is UNKNOWN — never guessed.
# Time-sensitive topics (tech, medicine, AI, finance…) require <= 6-month-old
# sources; everything else tolerates 2 years.
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

TIME_SENSITIVE = [
    "ai", "llm", "model", "tech", "software", "medicine", "health", "drug",
    "finance", "market", "policy", "law", "election", "security", "startup",
    "company", "regulation", "crypto", "war", "covid",
]

_ABS_RE = re.compile(r"/abs/(\d{2})(\d{2})\.(\d{4,5})")
_ISO_RE = re.compile(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})")
_SLASH_RE = re.compile(r"[-/](20\d{2})/(\d{2})(?:/|$)")


def _date_from_url(url: str) -> datetime | None:
    m = _ABS_RE.search(url)  # arxiv.org/abs/YYMM.xxxxx — 2-digit year, 2-digit month
    if m:
        return datetime(2000 + int(m.group(1)), int(m.group(2)), 1)
    m = _ISO_RE.search(url)
    if m:
        y, mo, d = map(int, m.groups())
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return datetime(y, mo, d)
    m = _SLASH_RE.search(url)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), 1)
    return None


async def temporal_verify(claim: str, sources: Optional[List[Union[str, Dict[str, Any]]]] = None, dated_pages: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    sources = sources or []
    """URL-date check PLUS page-metadata dates (from deep_read's published_date).

    dated_pages: list of {"url", "published_date"} — lets temporal date pages
    whose URL itself carries no date (the v1 UNKNOWN case is now resolvable)."""
    from datetime import date as _date
    now = datetime.now()
    dated, undated = [], 0
    for s in sources:
        url = s if isinstance(s, str) else (s.get("url") or "")
        dt = _date_from_url(url or "")
        if dt:
            dated.append({"url": url, "date": dt.isoformat(), "age_days": (now - dt).days})
        else:
            undated += 1
    seen_dated_urls = {d["url"] for d in dated}
    for p in (dated_pages or []):
        if not isinstance(p, dict) or not p.get("url") or p["url"] in seen_dated_urls:
            continue
        d = p.get("published_date") or p.get("date") or ""
        if isinstance(d, str) and len(d) >= 10:
            try:
                dt = datetime.fromisoformat(d[:10])
            except ValueError:
                dt = None
            if dt:
                dated.append({"url": p["url"], "date": dt.isoformat(), "age_days": (now - dt).days,
                              "date_source": "deep_read-page-metadata"})

    is_ts = any(k in claim.lower() for k in TIME_SENSITIVE)

    if not dated:
        return {
            "verdict": "UNKNOWN",
            "reason": "no publication date extractable from source URLs or page metadata",
            "time_sensitive": is_ts,
            "sources_checked": len(sources),
            "dated_sources": 0,
            "pages_date_checked": len(dated_pages or []),
            "recommendation": "mark the claim 'as of' or find a dated primary source",
        }

    newest = max(dated, key=lambda d: d["date"])
    age = newest["age_days"]
    max_age = 180 if is_ts else 730
    verdict = "CURRENT" if age <= max_age else "OUTDATED"
    return {
        "verdict": verdict,
        "age_days": age,
        "most_recent_source": newest["url"],
        "most_recent_date": newest["date"],
        "newest": {"url": newest["url"], "date": newest["date"], "date_source": newest.get("date_source", "url")},
        "dated_sources": len(dated),
        "time_sensitive": is_ts,
        "max_allowed_age_days": max_age,
        "sources_checked": len(dated),
        "undated_sources": undated,
    }