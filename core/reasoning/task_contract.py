"""Compile a checkable task contract for cheap / small host models.

Zhou et al. 2023 (least-to-most) and IFEval (Zhou et al. 2023) both show that
weak models follow *instance-specific, yes/no constraints* far better than a
generic 6-step ritual. This module is deterministic: no LLM, no network.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from core.eval.research_benchmarks import recommend_budget_tier
from core.reasoning.nuclear_prompt import break_down_prompt

ConstraintKind = Literal[
    "must_include",
    "must_not",
    "max_words",
    "format",
    "cite_quotes",
    "run_tests",
    "scope_files",
    "answer_directly",
]

NextAction = Literal["none", "evidence", "verify_constraints", "verify_tests"]


@dataclass(frozen=True)
class CheckableConstraint:
    """One machine-checkable requirement extracted from the user prompt."""

    id: str
    kind: ConstraintKind
    description: str
    terms: tuple[str, ...] = ()
    value: int = 0
    pattern: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskContract:
    """The only scaffold a cheap model should see before working."""

    goal: str
    deliverable: str
    constraints: tuple[CheckableConstraint, ...]
    stop_when: tuple[str, ...]
    do_not: tuple[str, ...]
    evidence_needed: tuple[str, ...]
    next_action: NextAction
    budget_tier: str
    max_tool_calls: int
    complexity: int

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["constraints"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in self.constraints]
        return data

    def constraint_lines(self) -> list[str]:
        return [f"[{c.id}] {c.description}" for c in self.constraints]


_CODE_HINTS = (
    "code",
    "repo",
    "implement",
    "fix",
    "debug",
    "pytest",
    "ruff",
    "patch",
    "refactor",
    "function",
    "class ",
    "mcp",
    "api",
)
_RESEARCH_HINTS = (
    "research",
    "cite",
    "citation",
    "source",
    "paper",
    "benchmark",
    "evidence",
    "url",
    "according to",
    "latest",
    "current",
)
_FORMAT_HINTS = {
    "json": "json",
    "markdown": "markdown",
    "patch": "patch",
    "diff": "patch",
    "bullet": "bullets",
    "bullets": "bullets",
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _complexity(prompt: str) -> int:
    score = 1
    lower = prompt.lower()
    if len(prompt) > 600:
        score += 1
    if any(term in lower for term in _CODE_HINTS):
        score += 1
    if any(term in lower for term in _RESEARCH_HINTS):
        score += 1
    if any(term in lower for term in ("production", "security", "auth", "migration")):
        score += 1
    return max(1, min(score, 5))


def _extract_files(prompt: str) -> tuple[str, ...]:
    found = re.findall(
        r"(?:files?:\s*|only\s+|in\s+)([\w./-]+\.(?:py|ts|js|tsx|jsx|md|toml|yml|yaml|json))", prompt, flags=re.I
    )
    found += re.findall(r"`([\w./-]+\.(?:py|ts|js|tsx|jsx|md|toml|yml|yaml|json))`", prompt)
    seen: list[str] = []
    for item in found:
        if item not in seen:
            seen.append(item)
    return tuple(seen[:6])


def _max_words(prompt: str) -> int:
    match = re.search(r"(?:at most|no more than|≤|<=)\s*(\d+)\s+words", prompt, flags=re.I)
    if match:
        return max(1, min(int(match.group(1)), 2000))
    return 0


def _negations(prompt: str) -> tuple[str, ...]:
    lines = re.findall(
        r"(?:do not|don't|dont|never|without|avoid)\s+([^.;\n]{3,80})",
        prompt,
        flags=re.I,
    )
    cleaned = []
    for line in lines:
        item = _clean(line).rstrip(".")
        if item and item.lower() not in {c.lower() for c in cleaned}:
            cleaned.append(item)
    return tuple(cleaned[:6])


def _must_phrases(prompt: str) -> tuple[str, ...]:
    lines = re.findall(
        r"(?:must|need to|needed|required to|have to)\s+([^.;\n]{3,80})",
        prompt,
        flags=re.I,
    )
    cleaned = []
    for line in lines:
        item = _clean(line).rstrip(".")
        if item and item.lower() not in {c.lower() for c in cleaned}:
            cleaned.append(item)
    return tuple(cleaned[:6])


def _detect_format(prompt: str) -> str:
    lower = prompt.lower()
    for needle, label in _FORMAT_HINTS.items():
        if needle in lower:
            return label
    return ""


def compile_task_contract(prompt: str, complexity: int = 0) -> TaskContract:
    """Turn a user prompt into a short, checkable contract."""
    cleaned = _clean(prompt)
    if not cleaned:
        raise ValueError("prompt is required")

    breakdown = break_down_prompt(cleaned)
    level = complexity if complexity > 0 else _complexity(cleaned)
    budget = recommend_budget_tier(cleaned, level)
    lower = cleaned.lower()
    is_code = any(term in lower for term in _CODE_HINTS)
    is_research = any(term in lower for term in _RESEARCH_HINTS)
    files = _extract_files(cleaned)
    word_cap = _max_words(cleaned)
    fmt = _detect_format(cleaned)
    must = _must_phrases(cleaned)
    banned = _negations(cleaned)

    constraints: list[CheckableConstraint] = []

    for index, phrase in enumerate(must, 1):
        terms = tuple(token for token in re.findall(r"[A-Za-z0-9_+.-]{4,}", phrase)[:6])
        constraints.append(
            CheckableConstraint(
                id=f"must_{index}",
                kind="must_include",
                description=f"Satisfy: {phrase}",
                terms=terms or (phrase[:40],),
            )
        )

    for index, phrase in enumerate(banned, 1):
        terms = tuple(token for token in re.findall(r"[A-Za-z0-9_+.-]{4,}", phrase)[:6])
        constraints.append(
            CheckableConstraint(
                id=f"not_{index}",
                kind="must_not",
                description=f"Do not: {phrase}",
                terms=terms or (phrase[:40],),
            )
        )

    if word_cap:
        constraints.append(
            CheckableConstraint(
                id="max_words",
                kind="max_words",
                description=f"Keep the answer to at most {word_cap} words.",
                value=word_cap,
            )
        )

    if fmt:
        constraints.append(
            CheckableConstraint(
                id="format",
                kind="format",
                description=f"Use {fmt} as the primary output format.",
                pattern=fmt,
            )
        )

    if files:
        constraints.append(
            CheckableConstraint(
                id="scope_files",
                kind="scope_files",
                description="Touch only these files: " + ", ".join(files),
                terms=files,
            )
        )

    if is_research:
        constraints.append(
            CheckableConstraint(
                id="cite_quotes",
                kind="cite_quotes",
                description="Ground factual claims in verbatim quotes with URLs. No quote, no citation.",
            )
        )

    if is_code and any(term in lower for term in ("test", "pytest", "validate", "ruff")):
        constraints.append(
            CheckableConstraint(
                id="run_tests",
                kind="run_tests",
                description="Do not claim completion until allowlisted tests/lint have a passing log.",
            )
        )

    if level <= 1 and not is_code and not is_research:
        constraints.append(
            CheckableConstraint(
                id="direct",
                kind="answer_directly",
                description="Answer directly. Do not call tools.",
            )
        )

    constraints = constraints[:8]
    if not constraints:
        constraints.append(
            CheckableConstraint(
                id="goal",
                kind="must_include",
                description="Address the stated goal directly.",
                terms=tuple(token for token in cleaned.split()[:4] if len(token) > 3),
            )
        )

    if is_research:
        deliverable = "Cited answer with verbatim quotes and URLs"
        next_action: NextAction = "evidence"
        evidence = ("Primary-source quotes from live pages.",)
    elif is_code:
        deliverable = "Minimal patch or code plus a validation log"
        next_action = "none"
        evidence = ("Targeted test or lint output.",)
    else:
        deliverable = "Direct answer that satisfies every constraint"
        next_action = "none"
        evidence = ()

    stop_when = [
        "Every checkable constraint passes, or a blocker is named.",
        "No extra tool call would change the answer enough to justify its cost.",
    ]
    if is_code:
        stop_when.insert(0, "Relevant tests/lint pass, or failures are reproduced and owned.")
    if is_research:
        stop_when.insert(0, "Each factual claim has a quote+URL or is labeled assumption.")

    do_not = [
        "Do not invent citations, quality scores, or SUCCESS JSON in place of the answer.",
        "Do not expand scope beyond the goal.",
    ]
    do_not.extend(f"Do not {item}" for item in banned[:3])

    return TaskContract(
        goal=breakdown.user_goal,
        deliverable=deliverable,
        constraints=tuple(constraints),
        stop_when=tuple(dict.fromkeys(stop_when)),
        do_not=tuple(dict.fromkeys(do_not))[:6],
        evidence_needed=evidence,
        next_action=next_action,
        budget_tier=budget.tier,
        max_tool_calls=budget.max_tool_calls,
        complexity=level,
    )


def contract_from_dict(raw: dict[str, Any], fallback_prompt: str = "") -> TaskContract:
    """Rebuild a contract from persisted JSON, falling back to recompile."""
    prompt = fallback_prompt or str(raw.get("goal") or "task")
    base = compile_task_contract(prompt, int(raw.get("complexity") or 0))
    items = raw.get("constraints") or []
    if not isinstance(items, list) or not items:
        return base
    constraints: list[CheckableConstraint] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        kind = item.get("kind") or "must_include"
        if kind not in (
            "must_include",
            "must_not",
            "max_words",
            "format",
            "cite_quotes",
            "run_tests",
            "scope_files",
            "answer_directly",
        ):
            kind = "must_include"
        constraints.append(
            CheckableConstraint(
                id=str(item.get("id", f"c{i}")),
                kind=kind,
                description=str(item.get("description", "")),
                terms=tuple(item.get("terms") or ()),
                value=int(item.get("value") or 0),
                pattern=str(item.get("pattern") or ""),
            )
        )
    if not constraints:
        return base
    nxt = raw.get("next_action") or base.next_action
    if nxt not in ("none", "evidence", "verify_constraints", "verify_tests"):
        nxt = base.next_action
    return TaskContract(
        goal=str(raw.get("goal") or base.goal),
        deliverable=str(raw.get("deliverable") or base.deliverable),
        constraints=tuple(constraints),
        stop_when=tuple(raw.get("stop_when") or base.stop_when),
        do_not=tuple(raw.get("do_not") or base.do_not),
        evidence_needed=tuple(raw.get("evidence_needed") or base.evidence_needed),
        next_action=nxt,
        budget_tier=str(raw.get("budget_tier") or base.budget_tier),
        max_tool_calls=int(raw.get("max_tool_calls") or base.max_tool_calls),
        complexity=int(raw.get("complexity") or base.complexity),
    )


def contract_markdown(contract: TaskContract) -> str:
    """Render a short contract a small model can follow in one screen."""
    lines = [
        "# Task Contract",
        "",
        f"**Goal:** {contract.goal}",
        f"**Deliverable:** {contract.deliverable}",
        f"**Next action:** `{contract.next_action}`",
        f"**Budget:** `{contract.budget_tier}` ≤ {contract.max_tool_calls} tool calls",
        "",
        "## Constraints (must pass)",
    ]
    lines.extend(f"- {line}" for line in contract.constraint_lines())
    lines.extend(["", "## Do not"])
    lines.extend(f"- {item}" for item in contract.do_not)
    lines.extend(["", "## Stop when"])
    lines.extend(f"- {item}" for item in contract.stop_when)
    if contract.evidence_needed:
        lines.extend(["", "## Evidence needed"])
        lines.extend(f"- {item}" for item in contract.evidence_needed)
    return "\n".join(lines)
