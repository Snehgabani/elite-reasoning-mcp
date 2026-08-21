# src/leverage/deep_read.py
# LIVE FULL-PAGE READING — the "article reader" tier.
#
# No browser needed: direct HTTP fetch + HTML→text extraction, then the
# Jina Reader fallback (free, keyless) for pages that block bots. Returns the
# extracted text so downstream tools (consensus, temporal) can reason on the
# FULL article, not a 200-char snippet.
from typing import Any, Dict

import httpx

UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}
MAX_TEXT = 8000
MIN_TEXT = 200


def _extract_text(html: str) -> tuple[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "form"]):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else ""
    parts = [t.get_text(" ", strip=True) for t in soup.find_all(["p", "h1", "h2", "h3", "blockquote"])]
    return title, " ".join(p for p in parts if p)[:MAX_TEXT]


def _extract_pub_date(html: str) -> str | None:
    """Pull a publication date from page metadata (article:published_time,
    og:published_time, JSON-LD datePublished, <time datetime>) — returns ISO
    date (YYYY-MM-DD) or None. This is what lets temporal_verify date real
    pages whose URL carries no date."""
    import re

    from bs4 import BeautifulSoup
    try:
        soup = BeautifulSoup(html, "html.parser")
        for attr in ("article:published_time", "og:published_time", "article:modified_time"):
            m = soup.find("meta", attrs={"property": attr}) or soup.find("meta", attrs={"name": attr})
            content = (m or {}).get("content") if hasattr(m, "get") else None
            if content:
                iso = re.match(r"(\d{4}-\d{2}-\d{2})", str(content))
                if iso:
                    return iso.group(1)
        t = soup.find("time", attrs={"datetime": True})
        if t and t.get("datetime"):
            iso = re.match(r"(\d{4}-\d{2}-\d{2})", t["datetime"])
            if iso:
                return iso.group(1)
    except Exception as exc:
        # Explicit non-fatal exception suppression
        _ = str(exc)
    return None


async def deep_read_url(url: str, question: str = "", query: str = "") -> Dict[str, Any]:
    target_q = question or query
    if not url.startswith(("http://", "https://")):
        return {"url": url, "extracted": False, "error": "invalid_scheme"}

    # Pass 1: direct HTTP fetch + text extraction
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=UA) as c:
            r = await c.get(url)
        if r.status_code == 200 and len(r.text) > 200:
            title, text = _extract_text(r.text)
            if len(text) >= MIN_TEXT:
                pub = _extract_pub_date(r.text)
                out = {
                    "url": url, "provider": "direct-http", "title": title,
                    "full_text_length": len(text), "text": text[:MAX_TEXT],
                    "extracted": True,
                }
                if pub:
                    out["published_date"] = pub
                    out["date_source"] = "page-metadata"
                return out
    except Exception as exc:
        # Explicit non-fatal exception suppression
        _ = str(exc)

    # Pass 2: Jina Reader free fallback (renders JS, returns markdown text)
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as c:
            rr = await c.get(f"https://r.jina.ai/{url}")
        if rr.status_code == 200 and len(rr.text) >= MIN_TEXT:
            t = rr.text
            title = t.splitlines()[0].strip()[:200] if t else ""
            return {
                "url": url, "provider": "jina-reader", "title": title,
                "full_text_length": len(t), "text": t[:MAX_TEXT],
                "extracted": True,
            }
    except Exception as exc:
        # Explicit non-fatal exception suppression
        _ = str(exc)

    return {"url": url, "extracted": False, "error": "unreadable", "text": ""}
