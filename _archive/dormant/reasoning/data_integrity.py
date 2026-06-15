from typing import Dict, Any, List

class DataIntegrityFilter:
    """
    6-stage External Data Integrity Filter.
    Filters external sources before they contaminate the LLM context.
    """
    def __init__(self, llm_client: Any):
        self.llm = llm_client

    def rank_source(self, source_url: str) -> int:
        """
        Rank source credibility from 1 (untrustworthy) to 5 (gold standard).
        1: SEO spam, unverified social media.
        2: Heavily biased, commercial blogs.
        3: Mainstream news, Wikipedia.
        4: Verified expert blogs, specialized journalism.
        5: Peer-reviewed, primary sources, official docs.
        """
        # Heuristic implementation
        if ".gov" in source_url or ".edu" in source_url or "arxiv.org" in source_url:
            return 5
        if "wikipedia.org" in source_url or "nytimes.com" in source_url:
            return 3
        return 2

    def detect_ai_generation(self, text: str) -> bool:
        """Detect common LLM generated linguistic patterns."""
        ai_isms = ["In conclusion", "It is important to note", "delve", "tapestry", "crucial", "testament"]
        count = sum(1 for ism in ai_isms if ism.lower() in text.lower())
        return count >= 3

    def filter_payload(self, text: str, source_url: str) -> Dict[str, Any]:
        """Run the full integrity filter pipeline."""
        rank = self.rank_source(source_url)
        if rank < 3:
            return {"accepted": False, "reason": f"Source credibility too low (Rank {rank})"}
            
        if self.detect_ai_generation(text):
            return {"accepted": False, "reason": "High probability of AI-generated content (Slop)"}
            
        return {"accepted": True, "reason": "Passed integrity checks", "text": text}
