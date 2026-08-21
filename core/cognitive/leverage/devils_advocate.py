# src/leverage/devils_advocate.py
# ADVERSARIAL VERIFICATION LOOP — DESTROY the draft, then revise it.
# Mechanism from the adversarial-verification research line (cf. multi-agent
# debate, Du et al. arXiv:2305.14325) — a hostile fact-checker critiques the
# draft with severity scores, and the draft is revised until no major
# critiques remain (bounded rounds; always returns SOMETHING).
import json
import re
from typing import Any, Dict, List, Optional, Union

from langchain_core.messages import HumanMessage, SystemMessage

from core.cognitive.agent_nodes import SOLVER_LLM

ADVOCATE_PROMPT = """You are a hostile fact-checker. Your job is to DESTROY the draft answer below.

DRAFT ANSWER:
{draft}

SOURCES:
{sources}

Find:
1. Contradictions between the answer and the sources
2. Claims not supported by any source (unsupported leaps)
3. Logical fallacies or circular reasoning
4. Outdated information (dates, version numbers, regime changes)
5. Alternative interpretations or counter-evidence the answer ignores

Return STRICT JSON only, no prose:
{{
  "critiques": [
    {{"severity": 0.0..1.0, "critique": "...", "suggested_revision": "..."}}
  ],
  "verdict": "REVISED" or "SUPPORTED"
}}"""

REVISE_PROMPT = """Revise the draft below to resolve the critiques. Keep what survives, fix what is attacked. Output ONLY the revised answer text.

DRAFT:
{draft}

CRITIQUES:
{critiques}"""


async def _advocate_llm(messages):
    for attempt in (1, 2):
        try:
            return await SOLVER_LLM.ainvoke(messages)
        except Exception:
            if attempt == 2:
                return None
    return None


def _txt(resp) -> str:
    c = resp.content
    if c:
        return c
    return (resp.additional_kwargs or {}).get("reasoning_content") or "[empty model response]"


def _loose_json(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {"parse_error": raw[:300]}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"parse_error": raw[:300], "raw": m.group(0)[:1200]}


async def devils_advocate(draft_answer: str, sources: List[Union[str, Dict[str, Any]]]) -> dict:
    src_txt = "\n".join(s if isinstance(s, str) else s.get("url", "") for s in (sources or []))
    if not src_txt:
        src_txt = "(no sources provided)"
    prompt = ADVOCATE_PROMPT.format(draft=draft_answer[:6000], sources=src_txt[:4000])
    resp = await _advocate_llm(
        [SystemMessage("You are an adversarial verification engine. Output ONLY valid JSON."), HumanMessage(prompt)]
    )
    if resp is None:
        return {"parse_error": "llm_unavailable"}
    return _loose_json(_txt(resp))


async def revision_loop(
    draft_answer: str, sources: Optional[List[Union[str, Dict[str, Any]]]] = None, max_rounds: int = 2
) -> dict:
    sources = sources or []
    """Critique -> revise until no major (>=0.6) critiques, bounded by max_rounds."""
    current = draft_answer
    history: List[dict] = []
    for _ in range(max_rounds):
        critique = await devils_advocate(current, sources)
        critique.setdefault("verdict", "SUPPORTED")
        history.append(critique)
        crits = critique.get("critiques") or []
        major = [c for c in crits if isinstance(c, dict) and float(c.get("severity", 0)) >= 0.6]
        if not major:
            break
        rev_prompt = REVISE_PROMPT.format(
            draft=current[:6000],
            critiques=json.dumps(
                [{"severity": c.get("severity"), "critique": c.get("critique")} for c in major], indent=1
            )[:4000],
        )
        resp = await _advocate_llm(
            [
                SystemMessage("You are a ruthless editor. Keep the answer concise and evidence-bound."),
                HumanMessage(rev_prompt),
            ]
        )
        if resp is not None:
            current = _txt(resp).strip() or current
    return {
        "rounds": len(history),
        "history": history,
        "final_draft": current,
        "revised": len(history) > 0
        and history[-1].get("critiques")
        and any(isinstance(c, dict) and float(c.get("severity", 0)) >= 0.6 for c in history[-1].get("critiques", []))
        is False,
    }
