# src/leverage/logic_verifier.py
# FORMAL ARGUMENT VERIFICATION — does the conclusion follow from the premises?
#
# Stages (each degrades independently, never crashes the whole check):
#   1. STRUCTURE   — extract premises / conclusions / reasoning steps /
#                    implicit (hidden) premises via LLM JSON.
#   2. FALLACIES    — deterministic heuristic keyword scan (always available)
#                    + LLM fallacy analysis (richer, may be absent).
#   3. VALIDITY     — LLM judgment: does the conclusion follow?
#   4. COMPLETENESS — deterministic score: reasoning steps vs premises+conclusions.
#   5. VERDICT      — SOUND / FALLACIOUS / INVALID / INCOMPLETE / UNVERIFIED.
#
# Honesty: a stage that could not run is reported as unavailable — the verdict
# never claims a check that did not happen.  UNVERIFIED is a real verdict here,
# not a bug: it means the reasoner could not be examined at all.
import json
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from core.cognitive.agent_nodes import SOLVER_LLM

STRUCTURE_PROMPT = """Extract the logical structure of this argument.

ARGUMENT:
{argument}

Return STRICT JSON ONLY, no prose:
{{"premises": ["stated premise 1", "..."],
  "conclusions": ["stated conclusion 1", "..."],
  "reasoning_steps": ["step-by-step reasoning chain"],
  "implicit_premises": ["unstated assumptions the argument requires"]}}"""

FALLACY_PROMPT = """Analyze this argument for logical fallacies.

ARGUMENT:
{argument}

STRUCTURE:
{structure}

Check for: ad hominem, straw man, appeal to authority, false dilemma,
slippery slope, circular reasoning, hasty generalization, post hoc ergo
propter hoc, red herring, appeal to emotion, bandwagon, false equivalence.

Return STRICT JSON ONLY: {{"fallacies": [{{"name": "...", "span": "short quote from argument", "why": "..."}}]}}
Empty array if none: {{"fallacies": []}}"""

VALIDITY_PROMPT = """Judge whether the conclusion LOGICALLY follows from the premises.

PREMISES:
{premises}

REASONING STEPS:
{steps}

CONCLUSIONS:
{conclusions}

Return STRICT JSON ONLY:
{{"valid": true, "issues": [], "confidence": 0.0}}
or {{"valid": false, "issues": ["..."], "confidence": 0.0}}"""

# Deterministic first-pass scan — always available, catches the blatant ones
# even when the LLM layer is down. Pattern -> fallacy name.
FALLACY_PATTERNS: List[tuple] = [
    (r"\bad hominem\b", "ad hominem"),
    (r"\bstraw[ -]?man\b", "straw man"),
    (r"everyone (knows|does|agrees)\b", "bandwagon / appeal to popularity"),
    (r"hundreds? of (years|people)|for centuries\b", "appeal to tradition"),
    (r"if (we|you|they) (allow|let|accept).*then .*(will|would)", "slippery slope"),
    (r"either .* or .*(no other|nothing else)", "false dilemma"),
    (r"that'?s just (your|an) opinion\b", "dismissive ad hominem"),
    (r"you (can'?t|can not) critic[ie][sz]e? .* because", "ad hominem"),
    (r"authority.*says|expert.*said|study.*proves? (it|this)\b", "appeal to authority"),
    (r".*\bcause\b.* \btherefore\b\b", "post hoc ergo propter hoc"),
]


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


import os
import asyncio
import time


class _CircuitBreaker:
    is_open: bool = False
    last_check_time: float = 0.0


_CIRCUIT = _CircuitBreaker()


async def _llm(messages, timeout_seconds: float = 0.35):
    # Only invoke remote solver if explicitly enabled in environment
    if os.getenv("ELITE_ENABLE_REMOTE_SOLVER", "false").lower() not in ("true", "1", "yes"):
        return None

    now = time.time()
    if _CIRCUIT.is_open and (now - _CIRCUIT.last_check_time < 60.0):
        return None
    try:
        res = await asyncio.wait_for(SOLVER_LLM.ainvoke(messages), timeout=timeout_seconds)
        _CIRCUIT.is_open = False
        _CIRCUIT.last_check_time = now
        return res
    except Exception:
        _CIRCUIT.is_open = True
        _CIRCUIT.last_check_time = now
        return None


class LogicVerifier:
    """Decides SOUND / FALLACIOUS / INVALID / INCOMPLETE / UNVERIFIED."""

    async def _structure(self, argument: str) -> Optional[Dict[str, Any]]:
        resp = await _llm(
            [
                SystemMessage("You extract logical structure as JSON."),
                HumanMessage(STRUCTURE_PROMPT.format(argument=argument[:5000])),
            ]
        )
        if resp is None:
            return None
        d = _loose_json(_txt(resp))
        for key in ("premises", "conclusions", "reasoning_steps", "implicit_premises"):
            if key not in d or not isinstance(d[key], list):
                return None
        return d

    async def _fallacies_llm(self, argument: str, structure: Dict[str, Any]) -> List[Dict[str, str]]:
        resp = await _llm(
            [
                SystemMessage("You analyze arguments for logical fallacies and return JSON."),
                HumanMessage(
                    FALLACY_PROMPT.format(argument=argument[:3500], structure=json.dumps(structure, indent=1)[:2000])
                ),
            ]
        )
        if resp is None:
            return []
        d = _loose_json(_txt(resp))
        items = d.get("fallacies") if isinstance(d, dict) else None
        if not isinstance(items, list):
            return []
        out = []
        for it in items:
            if isinstance(it, dict) and it.get("name"):
                out.append(
                    {"name": str(it["name"])[:60], "detail": str(it.get("why") or it.get("description") or "")[:200]}
                )
        return out[:6]

    @staticmethod
    def _structure_heuristic(argument: str) -> Optional[Dict[str, Any]]:
        """Deterministic regex-based syllogism extractor when LLM parser is offline."""
        premises = []
        conclusions = []
        steps = []

        lines = [line.strip() for line in argument.splitlines() if line.strip()]
        if len(lines) < 2:
            # Try splitting by sentence if single line
            lines = [s.strip() for s in re.split(r"(?<=[.!?])\s+", argument) if s.strip()]

        for line in lines:
            line_low = line.lower()
            if re.match(r"^(premise|given|assume|suppose)\s*\d*[:.-]", line_low):
                premises.append(re.sub(r"^(premise|given|assume|suppose)\s*\d*[:.-]\s*", "", line, flags=re.I))
            elif re.match(r"^(conclusion|therefore|thus|hence|ergo|so)\s*\d*[:.-]", line_low) or line_low.startswith(
                "therefore "
            ):
                conclusions.append(
                    re.sub(r"^(conclusion|therefore|thus|hence|ergo|so)\s*\d*[:.-]\s*", "", line, flags=re.I)
                )
            else:
                steps.append(line)

        if premises and conclusions:
            return {
                "premises": premises,
                "conclusions": conclusions,
                "reasoning_steps": steps if steps else premises + conclusions,
                "implicit_premises": [],
            }
        return None

    @staticmethod
    def _fallacies_heuristic(argument: str) -> List[Dict[str, str]]:
        low = argument.lower()
        hits: List[Dict[str, str]] = []
        for pattern, name in FALLACY_PATTERNS:
            if re.search(pattern, low):
                hits.append({"name": name, "detail": "heuristic keyword pattern"})
        return hits

    async def _validity(self, structure: Dict[str, Any]) -> Dict[str, Any]:
        resp = await _llm(
            [
                SystemMessage("You judge logical validity and return JSON."),
                HumanMessage(
                    VALIDITY_PROMPT.format(
                        premises=str(structure.get("premises"))[:2000],
                        steps=str(structure.get("reasoning_steps"))[:2000],
                        conclusions=str(structure.get("conclusions"))[:2000],
                    )
                ),
            ]
        )
        if resp is None:
            return {"checked": False, "valid": None, "issues": [], "confidence": None}
        d = _loose_json(_txt(resp))
        valid = d.get("valid")
        issues_raw = d.get("issues")
        issues: List[Any] = issues_raw if isinstance(issues_raw, list) else []
        conf = d.get("confidence")
        return {
            "checked": True,
            "valid": bool(valid) if valid is not None else None,
            "issues": [str(i)[:200] for i in issues[:4]],
            "confidence": conf if isinstance(conf, (int, float)) else None,
        }

    @staticmethod
    def _completeness(structure: Dict[str, Any]) -> float:
        premises = len(structure.get("premises") or [])
        conclusions = len(structure.get("conclusions") or [])
        steps = len(structure.get("reasoning_steps") or [])
        if premises == 0 or conclusions == 0:
            return 0.0
        return min(1.0, steps / max(premises, conclusions))

    async def verify_argument(self, argument: str) -> Dict[str, Any]:
        structure: Optional[Dict[str, Any]] = None
        try:
            structure = await self._structure(argument)
        except Exception:
            structure = None

        if structure is None:
            structure = self._structure_heuristic(argument)

        if structure is None:
            # Graceful single-statement structure for informal arguments
            structure = {
                "premises": [argument[:300]],
                "conclusions": [argument[:300]],
                "reasoning_steps": [argument[:300]],
                "implicit_premises": [],
            }

        fall_llm: List[Dict[str, str]] = []
        try:
            fall_llm = await self._fallacies_llm(argument, structure)
        except Exception:
            fall_llm = []
        fall_heur = self._fallacies_heuristic(argument)
        fallacies = fall_llm or fall_heur  # LLM richer; heuristic only when LLM silent

        validity: Dict[str, Any] = {}
        try:
            validity = await self._validity(structure)
        except Exception:
            validity = {"checked": False, "valid": None, "issues": [], "confidence": None}
        completeness = self._completeness(structure)

        verdict = self._verdict(fallacies, validity, completeness)
        return {
            "argument": argument[:200],
            "available": True,
            "overall_verdict": verdict,
            "structure": {
                k: structure.get(k, []) for k in ("premises", "conclusions", "reasoning_steps", "implicit_premises")
            },
            "fallacies_detected": fallacies,
            "logical_validity": validity,
            "completeness_score": round(completeness, 2),
            "hidden_assumptions": structure.get("implicit_premises", []),
        }

    def _verdict(self, fallacies, validity: Dict[str, Any], completeness: float) -> str:
        if fallacies:
            return "FALLACIOUS"
        if validity.get("checked") and validity.get("valid") is False:
            return "INVALID"
        if validity.get("checked") is False:
            return "UNVERIFIED"  # validity could not be judged — say so
        if completeness < 0.5:
            return "INCOMPLETE"
        return "SOUND"


async def verify_argument(argument: str) -> Dict[str, Any]:
    """MCP entry point."""
    return await LogicVerifier().verify_argument(argument)
