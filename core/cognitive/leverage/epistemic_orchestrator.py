# src/leverage/epistemic_orchestrator.py
# THE EPISTEMIC STACK — one call that runs the full verification pipeline:
#
#   triangulate -> deep_read -> synthesize -> devils-advocate revision -> temporal check
#
# Every verdict (consensus, critique count, temporal status) is appended to
# .ai/metrics/epistemic.jsonl so we can MEASURE the stack's actual effect on
# answer quality instead of trusting marketing percentages.
#
# Weak model + strong external verification: the model drafts, the machinery
# checks the draft against reality, repeatedly.
import asyncio
import json
import os
import time
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from core.cognitive.agent_nodes import SOLVER_LLM
from core.cognitive.leverage.claim_verify import verify_and_annotate
from core.cognitive.leverage.deep_read import deep_read_url
from core.cognitive.leverage.devils_advocate import revision_loop
from core.cognitive.leverage.expert_panel import expert_panel
from core.cognitive.leverage.temporal_check import temporal_verify
from core.cognitive.leverage.web_research import LiveWebResearcher

METRICS_FILE = ".ai/metrics/epistemic.jsonl"

SYNTHESIS_PROMPT = """Synthesize a rigorous, sourced answer to the question.

QUESTION:
{question}

SOURCE-PROVEN EVIDENCE (full-text extractions of real pages):
{evidence}

Rules:
- State ONLY what the evidence supports. No filler.
- Anything unsupported must be labeled [UNVERIFIED].
- Give the strongest sourced answer, then 2-3 true gaps in the evidence.
- Never invent citations. If you cite, use only the URLs above."""


async def _llm(messages, label: str = "stage"):
    """Retry-once LLM call; None on double failure (provider 429 / 5xx)."""
    for attempt in (1, 2):
        try:
            return await SOLVER_LLM.ainvoke(messages)
        except Exception as e:
            if attempt == 2 or "402" in str(e) or "401" in str(e):
                return None
    return None


def _txt(resp) -> str:
    c = resp.content
    return c if c else ((resp.additional_kwargs or {}).get("reasoning_content") or "[empty model response]")


def _log_epistemic(payload: dict) -> None:
    try:
        os.makedirs(".ai/metrics", exist_ok=True)
        with open(METRICS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception as e:
        # Suppress expected non-fatal exception
        pass


async def epistemic_research(
    question: str, depth: str = "deep", max_urls: Optional[int] = None, perspectives: Optional[list] = None
) -> Dict[str, Any]:
    t0 = time.time()
    tri = await LiveWebResearcher().search_and_triangulate(question, k=6)

    # ---- real sources only, never fabricated
    urls = [s["url"] for s in tri["sources"]]
    cap = max_urls or (3 if depth == "deep" else 1)
    reads = await asyncio.gather(*[deep_read_url(u, question) for u in urls[:cap]]) if urls[:cap] else []

    extra_parts = []
    for r in reads:
        if r.get("extracted"):
            extra_parts.append(f"SITE {r['url']}\n{r.get('text','')[:2000]}")
    extra = "\n\n".join(extra_parts) or "(no full text captured; evidence truncated)"

    draft_resp = await _llm(
        [SystemMessage("You are a rigorous research synthesizer."),
         HumanMessage(SYNTHESIS_PROMPT.format(question=question, evidence=extra))]
    )
    draft = _txt(draft_resp) if draft_resp else (
        "[MODEL LAYER UNAVAILABLE - answer below is raw evidence, unverified by synthesis]\n" + extra[:3000]
    )

    try:
        rev = await revision_loop(draft, tri["sources"], max_rounds=2)
    except Exception as e:
        rev = {"rounds": 0, "history": [{"parse_error": f"advocate unavailable: {e}"}], "final_draft": draft}

    dated_pages = [{"url": r["url"], "published_date": r["published_date"]} for r in reads if r.get("published_date")]
    temp = await temporal_verify(question, tri["sources"], dated_pages=dated_pages)

    panel = None
    if depth == "deep" and perspectives is None:
        try:
            panel = await expert_panel(question)   # economist/scientist/historian
        except Exception as e:
            panel = {"error": str(e)}

    # ---- CLAIM-LEVEL VERIFICATION (the final guarantee): split the revised
    # ---- draft into atomic claims, triangulate EACH, annotate the output.
    claims_stage: Optional[Dict[str, Any]] = None
    final_answer = rev["final_draft"]
    if depth == "deep":
        try:
            claims_stage = await verify_and_annotate(rev["final_draft"], max_claims=6)
            final_answer = claims_stage["final_answer"]
        except Exception as e:
            claims_stage = {"error": str(e)}

    result = {
        "question": question,
        "triangulation": {
            "num_sources": tri["num_sources"],
            "triangulated": tri["triangulated"],
            "degraded": tri["degraded"],
            "consensus_score": tri["consensus_score"],
            "providers_queried": tri["providers_queried"],
            "sources": tri["sources"],
        },
        "deep_reads": [{k: r.get(k) for k in ("url", "provider", "title", "full_text_length", "extracted")} for r in reads],
        "draft": draft,
        "revision": rev,
        "temporal": temp,
        "expert_panel": panel,
        "claim_verification": claims_stage,
        "final_answer": final_answer,
        "duration_seconds": round(time.time() - t0, 1),
    }

    cv: Optional[Dict[str, Any]] = claims_stage.get("claim_verification") if isinstance(claims_stage, dict) else None
    cv_counts: Any = cv.get("counts") if isinstance(cv, dict) else {}
    _log_epistemic({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "question": question,
        "num_sources": tri["num_sources"],
        "triangulated": tri["triangulated"],
        "consensus_score": tri["consensus_score"],
        "providers_queried": tri["providers_queried"],
        "temporal_verdict": temp["verdict"],
        "devils_rounds": rev["rounds"],
        "critiques_found": sum(len(h.get("critiques") or []) for h in rev["history"]),
        "claims_checked": (cv or {}).get("claims_checked", 0),
        "claims_verified": cv_counts.get("verified", 0),
        "duration_seconds": result["duration_seconds"],
    })
    return result