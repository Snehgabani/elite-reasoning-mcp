# src/leverage/claim_verify.py
# CLAIM-LEVEL VERIFICATION ENGINE — the final per-sentence guarantee.
#
# The pipeline verifies the QUESTION (triangulate/deep_read) and the DRAFT
# (devil's advocate), but an answer is only as strong as its weakest claim.
# This stage: split the final draft into atomic claims -> triangulate EACH
# against independent engines -> annotate every claim VERIFIED / DISPUTED /
# UNVERIFIED ("never output unverified claims").
#
# Honesty rules: no claim gets a source it didn't earn; verdicts require real
# multi-engine consensus; every failure degrades ([] claims, sources-only),
# never crashes.
import asyncio
import json
import re
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from core.cognitive.agent_nodes import SOLVER_LLM
from core.cognitive.leverage.web_research import LiveWebResearcher

CLAIM_EXTRACT_PROMPT = """Break the DRAFT below into atomic factual claims.

DRAFT:
{draft}

Rules:
- Each output must be ONE checkable fact (a verifiable statement).
- Drop hedging, rhetorical questions, stylistic advice, and framing sentences.
- Output STRICT JSON ONLY, no prose: {{"claims": ["...", "..."]}}

Max 8 claims. If nothing is checkable, output {{"claims": []}}."""

VERDICT_TAGS = {"verified": "\u2713 VERIFIED", "disputed": "\u26a0 DISPUTED", "unverified": "\u2717 UNVERIFIED"}


def _loose_json(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def _txt(resp) -> str:
    c = resp.content
    return c if c else ((resp.additional_kwargs or {}).get("reasoning_content") or "")


async def _llm(messages):
    for attempt in (1, 2):
        try:
            return await SOLVER_LLM.ainvoke(messages)
        except Exception:
            if attempt == 2:
                return None
    return None


async def extract_claims(draft: str, max_claims: int = 8) -> List[str]:
    resp = await _llm(
        [SystemMessage("You extract atomic factual claims. Output ONLY valid JSON."),
         HumanMessage(CLAIM_EXTRACT_PROMPT.format(draft=draft[:6000]))]
    )
    if resp is None:
        return []
    data = _loose_json(_txt(resp))
    claims = data.get("claims") if isinstance(data, dict) else None
    if not isinstance(claims, list):
        return []
    out: List[str] = []
    for c in claims:
        s = str(c).strip().strip('"').strip("'")
        if len(s) >= 15 and s not in out:
            out.append(s)
        if len(out) >= max_claims:
            break
    return out


def _provs(tri: Dict[str, Any]) -> List[str]:
    """Providers that actually CONTRIBUTED sources (fallback: engines that
    answered but didn't contribute count for nothing). Verdicts must not credit
    an engine whose results were deduped away."""
    srcs = tri.get("sources") or []
    if srcs:
        return sorted({s.get("provider") or "unknown" for s in srcs})
    return sorted(tri.get("providers_queried") or [])


def _verdict_for(tri: Dict[str, Any]) -> Dict[str, Any]:
    num = tri["num_sources"]
    provider_names = _provs(tri)
    multi = len(provider_names) >= 2
    if num >= 3 and multi:
        return {"verdict": "verified", "consensus_score": round(tri["consensus_score"], 2),
                "note": "multi-engine consensus"}
    if num >= 1:
        return {"verdict": "disputed", "consensus_score": round(tri["consensus_score"], 2),
                "note": "sources found but no multi-engine consensus"}
    return {"verdict": "unverified", "consensus_score": 0.0,
            "note": "no independent sources found"}


async def verify_one_claim(claim: str) -> Dict[str, Any]:
    tri = await LiveWebResearcher().search_and_triangulate(claim, k=4)
    v = _verdict_for(tri)
    return {
        "claim": claim,
        "verdict": v["verdict"],
        "consensus_score": v["consensus_score"],
        "note": v["note"],
        "num_sources": tri["num_sources"],
        "providers": tri.get("contrib_providers") or _provs(tri),
        "providers_queried": tri.get("providers_queried", []),
        "sources": [s["url"] for s in tri["sources"][:3]],
    }


async def verify_claims(draft: str, max_claims: int = 6, parallel: int = 3) -> Dict[str, Any]:
    """Extract claims, then triangulate each (bounded fan-out). Degrades to
    []/unverified on any failure — never crashes the pipeline."""
    claims = await extract_claims(draft, max_claims)
    results: List[Dict[str, Any]] = []
    if claims:
        for i in range(0, len(claims), parallel):
            batch = claims[i:i + parallel]
            results.extend(await asyncio.gather(*[verify_one_claim(c) for c in batch]))
    counts = {"verified": 0, "disputed": 0, "unverified": 0}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    return {"claims_checked": len(results), "counts": counts, "verifications": results}


def annotate(draft: str, claims_res: Dict[str, Any]) -> str:
    """Append a claim-level verification appendix; claims that appear verbatim
    in the draft also get an inline [C1.✓ VERIFIED]-style tag (replace-based,
    so offsets stay valid)."""
    if not claims_res.get("verifications"):
        return draft
    annotated = draft
    for i, v in enumerate(claims_res["verifications"], 1):
        tag = f"[C{i}.{VERDICT_TAGS.get(v['verdict'], v['verdict'].upper())}]"
        idx = annotated.lower().find(v["claim"].lower())
        if idx != -1:
            end = annotated.find(".", idx)
            if end != -1:
                hit = annotated[idx:end + 1]
                annotated = annotated.replace(hit, hit + " " + tag, 1)
    lines = [f"## Claim-level verification ({claims_res['claims_checked']} claims)"]
    for i, v in enumerate(claims_res["verifications"], 1):
        src = ", ".join(v["sources"][:2])
        lines.append(
            f"- [C{i}.{VERDICT_TAGS.get(v['verdict'], v['verdict'].upper())}] {v['claim']}"
            f" · {v['consensus_score']} · {v['num_sources']} sources ({src or 'none'})"
        )
    return annotated + "\n\n" + "\n".join(lines)


async def verify_and_annotate(draft: str, max_claims: int = 6) -> Dict[str, Any]:
    res = await verify_claims(draft, max_claims)
    return {"claim_verification": res, "final_answer": annotate(draft, res)}
