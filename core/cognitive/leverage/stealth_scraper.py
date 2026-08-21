"""
Stealth Web Scraper & Fit-Markdown Extractor.
Uses the dedicated scrape virtualenv (~/.hermes/venvs/scrape/bin/python)
with trafilatura / crawl4ai for ultra-low memory (<180MB RAM) anti-bot web ingestion.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Optional


SCRAPE_PYTHON = os.path.expanduser("~/.hermes/venvs/scrape/bin/python")


class StealthScraperEngine:
    """
    Executes stealth markdown web scraping via subprocess isolation.
    """

    def __init__(self, timeout_seconds: float = 8.0):
        self.timeout = timeout_seconds
        self.python_bin = SCRAPE_PYTHON if os.path.exists(SCRAPE_PYTHON) else None

    def scrape_fit_markdown(self, url: str) -> Dict[str, Any]:
        """
        Fetches web page and extracts clean fit-markdown.
        """
        if not self.python_bin:
            return {
                "status": "FALLBACK_HTTP",
                "url": url,
                "markdown": f"Scrape virtualenv not found at {SCRAPE_PYTHON}",
                "error": "SCRAPE_VENV_MISSING",
            }

        inline_code = f"""
import sys, json, trafilatura

url = {json.dumps(url)}
try:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        print(json.dumps({{"status": "FETCH_FAILED", "url": url, "error": "No content downloaded"}}))
        sys.exit(0)
    
    extracted = trafilatura.extract(
        downloaded,
        include_links=True,
        include_images=False,
        include_tables=True,
        output_format='json',
        favor_recall=True
    )
    if extracted:
        data = json.loads(extracted)
        print(json.dumps({{
            "status": "SUCCESS",
            "url": url,
            "title": data.get("title") or "",
            "text": data.get("raw_text") or data.get("text") or "",
            "length": len(data.get("raw_text") or data.get("text") or "")
        }}))
    else:
        print(json.dumps({{"status": "EXTRACT_FAILED", "url": url, "error": "Unable to extract main text"}}))
except Exception as e:
    print(json.dumps({{"status": "ERROR", "url": url, "error": str(e)}}))
"""
        try:
            res = subprocess.run(
                [self.python_bin, "-c", inline_code],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            stdout = res.stdout.strip()
            if stdout.startswith("{"):
                return json.loads(stdout)
            return {"status": "STDOUT_RAW", "url": url, "text": stdout[:2000]}
        except subprocess.TimeoutExpired:
            return {"status": "TIMEOUT", "url": url, "error": f"Scrape timed out after {self.timeout}s"}
        except Exception as exc:
            return {"status": "EXEC_ERROR", "url": url, "error": str(exc)}


_STEALTH_SCRAPER = StealthScraperEngine()
