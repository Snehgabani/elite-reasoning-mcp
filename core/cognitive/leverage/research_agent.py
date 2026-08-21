# src/leverage/research_agent.py
# AUTONOMOUS RESEARCH LOOPS — "searching vs researching" (GPT-Researcher pattern).
#
# Single-query search gives one perspective; this agent iterates:
#   decompose question -> sub-questions -> initial pass (search+deep_read each)
#   -> synthesize -> identify knowledge gaps -> research gaps -> re-synthesize
#   -> final report with real-source citations only.
#
# Honesty rules (shared with the epistemic stack):
#   - NEVER fabricate sources. Citations come only from URLs actually returned
#     by LiveWebResearcher and read this run.
#   - LLM failures degrade (single-pass, evidence-only, gaps_remaining=[]),
#     never crash, never fake iteration counts.
#   - If the LLM layer is down, `coverage_degraded` flips true so consumers
#     know the loop did NOT really iterate — it fell back to one direct pass.
import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from core.cognitive.agent_nodes import SOLVER_LLM
from core.cognitive.leverage.deep_read import deep_read_url
from core.cognitive.leverage.web_research import LiveWebResearcher

DECOMPOSE_PROMPT = """Break this research question into {max_sub} specific, searchable sub-questions that together would FULLY answer it.

QUESTION:
{question}

Output STRICT JSON ONLY, no prose: {{"subquestions": ["...", "..."]}}"""

SYNTHESIZE_PROMPT = """Synthesize a rigorous staged understanding of the research question.

QUESTION:
{question}

RESEARCH EVIDENCE (real page extractions, one block per sub-topic):
{evidence}

Rules:
- State ONLY what the evidence supports. Label anything inferable [INFERENCE].
- Note disagreements between sources if any.
- Output a detailed synthesis; end with 2-3 open questions the evidence does NOT answer yet."""

GAPS_PROMPT = """Given the research question and current synthesis, what specific knowledge gaps remain UNANSWERED?

QUESTION:
{question}

CURRENT SYNTHESIS:
{synthesis}

Output STRICT JSON ONLY: {{"gaps": ["...", "..."]}}
- Empty array means coverage is sufficient: output {{"gaps": []}}
- Each gap must be a fresh, answerable search question."""

REPORT_PROMPT = """Write a comprehensive research report answering the question.

QUESTION:
{question}

FINAL SYNTHESIS:
{synthesis}

SOURCES (real, fetched this run):
{sources}

Rules:
- Cite ONLY the sources above, by inline URL.
- Distinguish verified facts from interpretations; flag disagreement between sources.
- Include a short confidence assessment."""


def _loose_json(raw: str) -> dict:
    """Extract the first {...} block; empty dict on failure — never crash."""
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
    """Retry-once LLM call; None on double failure (provider 429 / 5xx)."""
    for attempt in (1, 2):
        try:
            return await SOLVER_LLM.ainvoke(messages)
        except Exception:
            if attempt == 2:
                return None
    return None


class AutonomousResearcher:
    """Iterative research agent: decompose -> pass -> gaps -> iterate -> report.

    search_fn async (query, k) -> triangulation dict (LiveWebResearcher shape).
    read_fn   async (url, question) -> dict (deep_read_url shape).
    """

    def __init__(
        self,
        search_fn=None,
        read_fn=None,
        max_iterations: int = 3,
        max_subquestions: int = 5,
        per_query_k: int = 4,
    ):
        self.search_fn = search_fn or (lambda q, k=5: LiveWebResearcher().search_and_triangulate(q, k=k))
        self.read_fn = read_fn or deep_read_url
        self.max_iterations = max_iterations
        self.max_subquestions = max_subquestions
        self.per_query_k = per_query_k

    async def _decompose(self, question: str) -> List[str]:
        resp = await _llm(
            [SystemMessage("You break research questions into searchable sub-questions."),
             HumanMessage(DECOMPOSE_PROMPT.format(question=question, max_sub=self.max_subquestions))]
        )
        if resp is None:
            return [question]  # honest fallback: single direct pass
        data = _loose_json(_txt(resp))
        sqs = data.get("subquestions") if isinstance(data, dict) else None
        if not isinstance(sqs, list):
            return [question]
        out: List[str] = []
        for s in sqs:
            st = str(s).strip().strip('"').strip("'")
            if len(st) >= 8 and st not in out:
                out.append(st)
            if len(out) >= self.max_subquestions:
                break
        return out or [question]

    async def _search_read(self, query: str) -> Dict[str, Any]:
        """One self-contained pass: live search + full reads; real URLs only."""
        tri = await self.search_fn(query, k=self.per_query_k)
        sources = tri.get("sources") or []
        reads = []
        if sources:
            reads = await asyncio.gather(*[self.read_fn(s["url"], query) for s in sources])
        read_urls: List[Dict[str, str]] = []
        parts: List[str] = []
        for r, s in zip(reads, sources):
            ok = bool(r and r.get("extracted") and r.get("text"))
            read_urls.append({"url": s["url"], "title": s.get("title", ""),
                              "provider": s.get("provider", ""), "read": str(ok)})
            if ok:
                parts.append(f"URL {s['url']}\n{(r.get('text') or '')[:2000]}")
        return {
            "query": query,
            "num_results": len(sources),
            "providers_queried": tri.get("providers_queried", []),
            "read_urls": read_urls,
            "evidence_parts": parts,
        }

    async def _synthesize(self, question: str, evidence_blocks: Dict[str, List[str]]) -> str:
        chunks = []
        for key, parts in evidence_blocks.items():
            if parts:
                chunks.append(f"## {key}\n" + "\n\n".join(parts))
        if not chunks:
            return "[NO EVIDENCE CAPTURED — nothing found for any subquestion]"
        resp = await _llm(
            [SystemMessage("You are a rigorous research synthesizer."),
             HumanMessage(SYNTHESIZE_PROMPT.format(
                 question=question, evidence="\n\n".join(chunks)[:24000]))]
        )
        if resp is None:
            return "[MODEL UNAVAILABLE — evidence-only synthesis, unverified by LLM]\n\n" + "\n\n".join(chunks)[:3000]
        return _txt(resp)

    async def _gaps(self, question: str, synthesis: str) -> List[str]:
        resp = await _llm(
            [SystemMessage("You only return JSON gap lists."),
             HumanMessage(GAPS_PROMPT.format(question=question, synthesis=synthesis[:5000]))]
        )
        if resp is None:
            return []  # stop iterating when the LLM is down — honest pass count
        data = _loose_json(_txt(resp))
        gaps = data.get("gaps") if isinstance(data, dict) else None
        if not isinstance(gaps, list):
            return []
        out = []
        for g in gaps:
            gs = str(g).strip().strip('"').strip("'")
            if gs:
                out.append(gs)
            if len(out) >= 3:
                break
        return out

    async def _write_report(self, question: str, synthesis: str,
                            findings: Dict[str, List[Dict[str, str]]]) -> str:
        all_urls = sorted({u["url"] for vs in findings.values() for u in vs if u.get("url")})
        resp = await _llm(
            [SystemMessage("You are a research analyst writing a final cited report."),
             HumanMessage(REPORT_PROMPT.format(
                 question=question, synthesis=synthesis[:8000],
                 sources="\n".join(f"- {u}" for u in all_urls) or "(no sources this run)"))]
        )
        if resp is None:
            return f"[MODEL UNAVAILABLE — raw evidence dump]\n\n{synthesis}\n\nSOURCE URLS:\n" + "\n".join(all_urls)
        return _txt(resp)

    async def research(self, question: str) -> Dict[str, Any]:
        subq = await self._decompose(question)
        decomposed = len(subq) > 1  # True => LLM alive and actually decomposed

        # First pass: every subquestion searched + deep-read (real URLs only).
        pass_results = await asyncio.gather(*[self._search_read(q) for q in subq])
        findings: Dict[str, List[Dict[str, str]]] = {}
        evidence_blocks: Dict[str, List[str]] = {}
        for sq, res in zip(subq, pass_results):
            findings[sq] = res["read_urls"]
            evidence_blocks[sq] = res["evidence_parts"]

        synthesis = await self._synthesize(question, evidence_blocks)

        iteration = 0
        gaps_researched: List[str] = []
        while iteration < self.max_iterations:
            gaps = await self._gaps(question, synthesis)
            if not gaps:
                break
            iteration += 1
            gap_results = await asyncio.gather(*[self._search_read(g) for g in gaps])
            for g, res in zip(gaps, gap_results):
                findings[g] = res["read_urls"]
                evidence_blocks[g] = res["evidence_parts"]
            gaps_researched = gaps
            synthesis = await self._synthesize(question, evidence_blocks)

        report = await self._write_report(question, synthesis, findings)
        all_urls = sorted({u["url"] for vs in findings.values() for u in vs if u.get("url")})
        return {
            "question": question,
            "decomposed": decomposed,
            "iterations": iteration,
            "subquestions": subq,
            "gaps_researched": gaps_researched,
            "coverage_degraded": not decomposed,
            "sources_consulted_count": len(all_urls),
            "sources_consulted": all_urls,
            "synthesis": synthesis,
            "report": report,
        }


async def autonomous_research(question: str, max_iterations: int = 3, max_subquestions: int = 5) -> Dict[str, Any]:
    """MCP entry point. Bounded fan-out; resilient to provider outages."""
    researcher = AutonomousResearcher(
        max_iterations=max(int(max_iterations), 1),
        max_subquestions=max(min(int(max_subquestions), 8), 1),
    )
    return await researcher.research(question)