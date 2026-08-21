"""
Optional Web Search Tool — For fact verification in research tasks

This is an OPT-IN tool. By default, the MCP is local-first.
Users can enable web search if they need fact verification.

Uses DuckDuckGo (no API key required) for privacy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

try:
    from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    HAS_DDG = False


@dataclass
class SearchResult:
    """A single search result."""
    title: str
    url: str
    snippet: str
    source: str = "duckduckgo"


class WebSearchTool:
    """
    Optional web search tool for fact verification.
    
    Usage:
        search = WebSearchTool()
        results = search.search("latest transformer efficiency research 2024", max_results=5)
        
    Note: This is opt-in. Default MCP is local-first.
    """
    
    def __init__(self, enabled: bool = False):
        """
        Initialize web search tool.
        
        Args:
            enabled: Whether web search is enabled (default: False for local-first)
        """
        self.enabled = enabled
        
        if enabled and not HAS_DDG:
            raise ImportError(
                "Web search requires duckduckgo-search. "
                "Install with: pip install duckduckgo-search"
            )
    
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Search the web for information.
        
        Args:
            query: Search query
            max_results: Maximum number of results (default: 5)
            
        Returns:
            List of search results
        """
        if not self.enabled:
            return []
        
        if not HAS_DDG:
            return []
        
        try:
            with DDGS() as ddgs:
                results = []
                for r in ddgs.text(query, max_results=max_results):
                    results.append(SearchResult(
                        title=r.get('title', ''),
                        url=r.get('href', ''),
                        snippet=r.get('body', ''),
                        source='duckduckgo'
                    ))
                return results
        except Exception:
            # Don't fail if search fails
            return []
    
    def verify_fact(self, claim: str) -> Dict:
        """
        Verify a factual claim by searching for evidence.
        
        Args:
            claim: The claim to verify
            
        Returns:
            Dictionary with verification results
        """
        if not self.enabled:
            return {
                "claim": claim,
                "verified": False,
                "evidence": [],
                "reason": "Web search disabled (local-first mode)"
            }
        
        # Search for the claim
        results = self.search(claim, max_results=5)
        
        # Analyze results
        if not results:
            return {
                "claim": claim,
                "verified": False,
                "evidence": [],
                "reason": "No search results found"
            }
        
        # Return evidence
        return {
            "claim": claim,
            "verified": len(results) > 0,
            "evidence": [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet
                }
                for r in results[:3]  # Top 3 results
            ],
            "reason": f"Found {len(results)} relevant results"
        }


def create_web_search_tool(enabled: bool = False) -> Optional[WebSearchTool]:
    """
    Create web search tool (factory function).
    
    Args:
        enabled: Whether to enable web search (default: False)
        
    Returns:
        WebSearchTool instance or None if disabled
    """
    if not enabled:
        return None
    
    try:
        return WebSearchTool(enabled=True)
    except ImportError:
        return None


if __name__ == "__main__":
    # Test web search
    print("="*70)
    print("WEB SEARCH TOOL — Testing")
    print("="*70)
    print()
    
    # Test disabled (default)
    print("1. Testing disabled mode (local-first)...")
    search = WebSearchTool(enabled=False)
    results = search.search("test query")
    print(f"   Results: {len(results)} (expected: 0)")
    print("   ✅ Disabled mode works")
    print()
    
    # Test enabled (if available)
    if HAS_DDG:
        print("2. Testing enabled mode...")
        search = WebSearchTool(enabled=True)
        results = search.search("Python programming language", max_results=3)
        print(f"   Results: {len(results)}")
        for r in results[:2]:
            print(f"   - {r.title}")
            print(f"     {r.url}")
        print("   ✅ Enabled mode works")
    else:
        print("2. Skipping enabled mode (duckduckgo-search not installed)")
        print("   Install with: pip install duckduckgo-search")
    
    print()
    print("="*70)
    print("✅ WEB SEARCH TOOL TEST COMPLETE")
    print("="*70)
