# src/leverage/web_research.py
# MULTI-SOURCE TRIANGULATION — consensus engine for weak-model fact checking.
#
# Real providers: DuckDuckGo HTML + Mojeek HTML + Wikipedia API + Jina Search
# (all free, keyless) — up to 4 independent engines per query, round-robin
# interleaved so no engine starves another.
#
# HONESTY RULE (was violated here before): if <3 real sources are found, we
# return `degraded: true` and the real sources — we NEVER fabricate citations.
# A fake arXiv URL is the exact hallucination this stack exists to prevent.
import asyncio
import json
import urllib.parse
from typing import Any, Dict, List

import httpx
from bs4 import BeautifulSoup

UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}


def _clean_ddg_redirect(url: str) -> str:
    if url.startswith("//duckduckgo.com/l/?uddg="):
        inner = url.split("uddg=")[1].split("&rut=")[0]
        return urllib.parse.unquote(inner)
    return url


class LiveWebResearcher:
    def __init__(self, timeout: float = 3.0, k: int = 5):
        self.timeout = timeout
        self.k = k

    async def _ddg(self, query: str) -> List[Dict[str, str]]:
        import urllib.parse
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=UA, follow_redirects=True) as c:
                r = await c.get(f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}")
            if r.status_code != 200:
                return []
            soup = BeautifulSoup(r.text, "html.parser")
            out: List[Dict[str, str]] = []
            for a in soup.find_all("a", class_="result__a", limit=self.k):
                url = _clean_ddg_redirect(a.get("href") or "")
                if url.startswith("http"):
                    out.append({"title": a.get_text(strip=True)[:180], "url": url, "provider": "duckduckgo"})
            return out
        except Exception:
            return []

    async def _jina_search(self, query: str) -> List[Dict[str, str]]:
        import urllib.parse
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers={**UA, "X-Respond-With": "json"}, follow_redirects=True) as c:
                r = await c.get(f"https://s.jina.ai/{urllib.parse.quote(query)}")
            if r.status_code != 200:
                return []
            data = r.json()
            out: List[Dict[str, str]] = []
            for item in (data.get("data") or [])[: self.k]:
                url = (item.get("url") or "").strip()
                if url.startswith("http"):
                    out.append({"title": (item.get("title") or "")[:180], "url": url, "provider": "jina"})
            return out
        except Exception:
            return []

    async def _mojeek(self, query: str) -> List[Dict[str, str]]:
        """Independent engine #2 — Mojeek HTML (keyless, own index)."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=UA, follow_redirects=True) as c:
                r = await c.get(f"https://www.mojeek.com/search?q={urllib.parse.quote(query)}")
            if r.status_code != 200:
                return []
            soup = BeautifulSoup(r.text, "html.parser")
            out: List[Dict[str, str]] = []
            for a in soup.select("ul.results-standard a.title")[: self.k]:
                url = a.get("href", "")
                if url.startswith("http"):
                    out.append({"title": a.get("title") or a.get_text(" ", strip=True)[:100],
                                "url": url, "provider": "mojeek"})
            return out
        except Exception:
            return []

    async def _wikipedia(self, query: str) -> List[Dict[str, str]]:
        """Facts backbone — Wikipedia search API (keyless, stable JSON)."""
        try:
            params = {"action": "query", "list": "search", "srsearch": query,
                      "format": "json", "srlimit": min(self.k, 10)}
            async with httpx.AsyncClient(timeout=self.timeout, headers=UA, follow_redirects=True) as c:
                r = await c.get("https://en.wikipedia.org/w/api.php", params=params)
            if r.status_code != 200:
                return []
            data = r.json()
            out: List[Dict[str, str]] = []
            for item in (data.get("query", {}).get("search") or [])[: self.k]:
                title = item.get("title") or ""
                if title:
                    url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
                    out.append({"title": title[:180], "url": url, "provider": "wikipedia"})
            return out
        except Exception:
            return []

    async def search_and_triangulate(self, query: str, k: int = 5) -> Dict[str, Any]:
        """Query 4 engines, dedupe by URL, and report an HONEST consensus."""
        self.k = k
        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    self._ddg(query), self._mojeek(query), self._wikipedia(query), self._jina_search(query),
                    return_exceptions=True
                ),
                timeout=4.0
            )
            ddg = results[0] if isinstance(results[0], list) else []
            mojeek = results[1] if isinstance(results[1], list) else []
            wiki = results[2] if isinstance(results[2], list) else []
            jina = results[3] if isinstance(results[3], list) else []
        except Exception:
            ddg, mojeek, wiki, jina = [], [], [], []
        seen, sources = set(), []
        batches = (ddg, mojeek, wiki, jina)
        # ROUND-ROBIN interleave (not priority-cap): later engines must not be
        # starved just because engine #1 answered k results first. Each engine
        # gets a slot per pass until we have k sources.
        for i in range(max((len(b) for b in batches), default=0)):
            for b in batches:
                if i < len(b) and b[i]["url"] not in seen:
                    seen.add(b[i]["url"])
                    sources.append(b[i])
                    if len(sources) >= k:
                        break
            if len(sources) >= k:
                break
        num = len(sources)
        counts = {"duckduckgo": len(ddg), "mojeek": len(mojeek), "wikipedia": len(wiki), "jina": len(jina)}
        return {
            "query": query,
            "providers_queried": [p for p, v in counts.items() if v],
            "contrib_providers": sorted({s["provider"] for s in sources}),
            "provider_counts": counts,
            "num_sources": num,
            "sources": sources,
            "consensus_score": min(1.0, num / 3.0),
            "triangulated": num >= 3,
            "degraded": num < 3,  # never fabricate to fake triangulation
        }

    async def triangulate(self, claim: str, k: int = 5) -> Dict[str, Any]:
        """Alias method for search_and_triangulate."""
        return await self.search_and_triangulate(claim, k=k)


async def live_web_search(query: str, num_results: int = 5) -> str:
    res = await LiveWebResearcher().search_and_triangulate(query, k=num_results)
    return json.dumps(res, indent=2)
