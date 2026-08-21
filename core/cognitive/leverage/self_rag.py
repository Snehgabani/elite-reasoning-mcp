# src/leverage/self_rag.py
# Self-RAG & Corrective RAG (CRAG) — Mid-Generation Epistemic Reflection

import json
from typing import Any, Dict, List

from core.cognitive.leverage.web_research import LiveWebResearcher


class SelfRAGEngine:
    def __init__(self):
        self.researcher = LiveWebResearcher()

    async def evaluate_and_correct(self, claim: str, retrieved_docs: List[str]) -> Dict[str, Any]:
        """
        Evaluates claim mid-generation with Self-RAG reflection tokens:
        [IsRel] (Is Relevant), [IsSup] (Is Supported), [IsUse] (Is Useful).
        Triggers CRAG corrective web search if unsupported.
        """
        doc_text = " ".join(retrieved_docs).lower()
        claim_lower = claim.lower()

        is_rel = "YES" if any(w in doc_text for w in claim_lower.split() if len(w) > 4) else "NO"
        is_sup = "YES" if is_rel == "YES" and len(doc_text) > 20 else "NO"
        is_use = "HIGH" if is_sup == "YES" else "LOW"

        corrected_claim = claim
        crag_triggered = False

        if is_sup == "NO":
            crag_triggered = True
            r_res = await self.researcher.search_and_triangulate(claim, k=2)
            sources = [s["url"] for s in r_res.get("sources", [])]
            if sources:
                corrected_claim = f"{claim} [needs quote from {sources[0]}]"
                is_sup = "UNVERIFIED"
                is_use = "LOW"
            else:
                corrected_claim = claim
                is_sup = "NO"
                is_use = "LOW"

        return {
            "original_claim": claim,
            "reflection_tokens": {"IsRel": is_rel, "IsSup": is_sup, "IsUse": is_use},
            "crag_triggered": crag_triggered,
            "corrected_claim": corrected_claim,
        }


async def self_rag_evaluate(
    query: str = "", retrieved_context: str = "", generated_response: str = "", claim: str = ""
) -> str:
    target = query or claim or generated_response or "default claim"
    engine = SelfRAGEngine()
    res = await engine.evaluate_and_correct(target, [])
    return json.dumps(res, indent=2)
