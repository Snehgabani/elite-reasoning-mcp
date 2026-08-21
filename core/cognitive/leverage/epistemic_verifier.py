# src/leverage/epistemic_verifier.py
import json
from typing import Any, Dict, List

from core.cognitive.leverage.web_research import LiveWebResearcher


class EpistemicVerifier:
    def __init__(self):
        self.researcher = LiveWebResearcher()

    async def verify_claims(self, claims: List[str] | str) -> Dict[str, Any]:
        if isinstance(claims, str):
            claims = [claims]
        verified_facts = []
        downgraded_assumptions = []
        flagged_biases = []

        for claim in claims:
            # Execute live research check
            res = await self.researcher.search_and_triangulate(claim, k=3)
            if res.get("triangulated"):
                verified_facts.append(
                    {"claim": claim, "provenance_urls": [s["url"] for s in res["sources"]], "status": "VERIFIED_FACT"}
                )
            else:
                downgraded_assumptions.append(
                    {
                        "claim": claim,
                        "reason": "Lacks 3+ live web source citations. Downgraded to [ASSUME].",
                        "status": "DOWNGRADED_TO_ASSUME",
                    }
                )

            if "obviously" in claim.lower() or "clearly" in claim.lower():
                flagged_biases.append(f"Cognitive Bias Flagged: Dogmatic phrasing in claim '{claim[:40]}...'")

        return {
            "verified_facts": verified_facts,
            "downgraded_assumptions": downgraded_assumptions,
            "flagged_biases": flagged_biases,
            "epistemic_score": round(len(verified_facts) / len(claims), 2) if claims else 1.0,
        }


async def epistemic_verify(claims: List[str] | str) -> str:
    if isinstance(claims, str):
        claims = [claims]
    verifier = EpistemicVerifier()
    res = await verifier.verify_claims(claims)
    return json.dumps(res, indent=2)
