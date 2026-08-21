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
    """One machine-checkable requirement extracted from the user prompt.

    Explicit constraints retain their exact source span. Constraints introduced
    by product policy are marked inferred so clients can distinguish user text
    from a conservative default.
    """

    id: str
    kind: ConstraintKind
    description: str
    terms: tuple[str, ...] = ()
    value: int = 0
    pattern: str = ""
    source_text: str = ""
    source_start: int = -1
    source_end: int = -1
    inferred: bool = False
    verification_method: str = "draft"
    extraction_confidence: float = 1.0

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
    schema_version: str = "1.1"

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


@dataclass(frozen=True)
class _SourceMatch:
    value: str
    source_text: str
    start: int
    end: int


def _first_match(prompt: str, pattern: str, *, group: int = 0) -> _SourceMatch | None:
    match = re.search(pattern, prompt, flags=re.I)
    if match is None:
        return None
    value = _clean(match.group(group)).rstrip(".")
    return _SourceMatch(value=value, source_text=match.group(0), start=match.start(), end=match.end())


def _clause_matches(prompt: str, pattern: str) -> tuple[_SourceMatch, ...]:
    matches: list[_SourceMatch] = []
    seen: set[str] = set()
    for match in re.finditer(pattern, prompt, flags=re.I):
        value = _clean(match.group(1)).rstrip(".")
        normalized = value.lower()
        if not value or normalized in seen:
            continue
        seen.add(normalized)
        matches.append(_SourceMatch(value, match.group(0), match.start(), match.end()))
        if len(matches) == 6:
            break
    return tuple(matches)


def _extract_files(prompt: str) -> tuple[tuple[str, ...], _SourceMatch | None]:
    pattern = r"(?:files?:\s*|only\s+|in\s+)([\w./-]+\.(?:py|ts|js|tsx|jsx|md|toml|yml|yaml|json))"
    matches = list(re.finditer(pattern, prompt, flags=re.I))
    matches += list(re.finditer(r"`([\w./-]+\.(?:py|ts|js|tsx|jsx|md|toml|yml|yaml|json))`", prompt, flags=re.I))
    matches.sort(key=lambda item: item.start())
    seen: list[str] = []
    selected = []
    for match in matches:
        item = match.group(1)
        if item not in seen:
            seen.append(item)
            selected.append(match)
        if len(seen) == 6:
            break
    if not selected:
        return (), None
    start = min(item.start() for item in selected)
    end = max(item.end() for item in selected)
    return tuple(seen), _SourceMatch(", ".join(seen), prompt[start:end], start, end)


def _max_words(prompt: str) -> tuple[int, _SourceMatch | None]:
    match = _first_match(prompt, r"(?:at most|no more than|≤|<=)\s*(\d+)\s+words", group=1)
    if match:
        return max(1, min(int(match.value), 2000)), match
    return 0, None


def _negations(prompt: str) -> tuple[_SourceMatch, ...]:
    return _clause_matches(prompt, r"(?:do not|don't|dont|never|without|avoid)\s+([^.;\n]{3,80})")


def _must_phrases(prompt: str) -> tuple[_SourceMatch, ...]:
    return _clause_matches(prompt, r"(?:must|need to|needed|required to|have to)\s+([^.;\n]{3,80})")


def _detect_format(prompt: str) -> tuple[str, _SourceMatch | None]:
    for needle, label in _FORMAT_HINTS.items():
        match = _first_match(prompt, rf"\b{re.escape(needle)}\b")
        if match:
            return label, match
    return "", None


def _hint_match(prompt: str, hints: tuple[str, ...]) -> _SourceMatch | None:
    for hint in hints:
        match = _first_match(prompt, re.escape(hint))
        if match:
            return match
    return None


def compile_task_contract(prompt: str, complexity: int = 0) -> TaskContract:
    """Turn a user prompt into a short, source-linked checkable contract."""
    source_prompt = prompt or ""
    cleaned = _clean(source_prompt)
    if not cleaned:
        raise ValueError("prompt is required")

    breakdown = break_down_prompt(cleaned)
    level = complexity if complexity > 0 else _complexity(cleaned)
    budget = recommend_budget_tier(cleaned, level)
    lower = cleaned.lower()
    is_code = any(term in lower for term in _CODE_HINTS)
    is_research = any(term in lower for term in _RESEARCH_HINTS)
    files, files_source = _extract_files(source_prompt)
    word_cap, word_source = _max_words(source_prompt)
    fmt, format_source = _detect_format(source_prompt)
    must = _must_phrases(source_prompt)
    banned = _negations(source_prompt)

    constraints: list[CheckableConstraint] = []

    for index, match in enumerate(must, 1):
        terms = tuple(token for token in re.findall(r"[A-Za-z0-9_+.-]{4,}", match.value)[:6])
        constraints.append(
            CheckableConstraint(
                id=f"must_{index}",
                kind="must_include",
                description=f"Satisfy: {match.value}",
                terms=terms or (match.value[:40],),
                source_text=match.source_text,
                source_start=match.start,
                source_end=match.end,
                verification_method="draft_terms",
                extraction_confidence=0.9,
            )
        )

    for index, match in enumerate(banned, 1):
        terms = tuple(token for token in re.findall(r"[A-Za-z0-9_+.-]{4,}", match.value)[:6])
        constraints.append(
            CheckableConstraint(
                id=f"not_{index}",
                kind="must_not",
                description=f"Do not: {match.value}",
                terms=terms or (match.value[:40],),
                source_text=match.source_text,
                source_start=match.start,
                source_end=match.end,
                verification_method="draft_terms",
                extraction_confidence=0.9,
            )
        )

    if word_cap:
        constraints.append(
            CheckableConstraint(
                id="max_words",
                kind="max_words",
                description=f"Keep the answer to at most {word_cap} words.",
                value=word_cap,
                source_text=word_source.source_text if word_source else "",
                source_start=word_source.start if word_source else -1,
                source_end=word_source.end if word_source else -1,
                verification_method="word_count",
            )
        )

    if fmt:
        constraints.append(
            CheckableConstraint(
                id="format",
                kind="format",
                description=f"Use {fmt} as the primary output format.",
                pattern=fmt,
                source_text=format_source.source_text if format_source else "",
                source_start=format_source.start if format_source else -1,
                source_end=format_source.end if format_source else -1,
                verification_method="output_format",
                extraction_confidence=0.9,
            )
        )

    if files:
        constraints.append(
            CheckableConstraint(
                id="scope_files",
                kind="scope_files",
                description="Touch only these files: " + ", ".join(files),
                terms=files,
                source_text=files_source.source_text if files_source else "",
                source_start=files_source.start if files_source else -1,
                source_end=files_source.end if files_source else -1,
                verification_method="git_diff",
                extraction_confidence=0.85,
            )
        )

    if is_research:
        research_source = _hint_match(source_prompt, _RESEARCH_HINTS)
        constraints.append(
            CheckableConstraint(
                id="cite_quotes",
                kind="cite_quotes",
                description="Ground factual claims in verbatim quotes with URLs. No quote, no citation.",
                source_text=research_source.source_text if research_source else "",
                source_start=research_source.start if research_source else -1,
                source_end=research_source.end if research_source else -1,
                inferred=True,
                verification_method="quote_and_url",
                extraction_confidence=0.75,
            )
        )

    if is_code and any(term in lower for term in ("test", "pytest", "validate", "ruff")):
        test_source = _hint_match(source_prompt, ("test", "pytest", "validate", "ruff"))
        constraints.append(
            CheckableConstraint(
                id="run_tests",
                kind="run_tests",
                description="Do not claim completion until allowlisted tests/lint have a passing log.",
                source_text=test_source.source_text if test_source else "",
                source_start=test_source.start if test_source else -1,
                source_end=test_source.end if test_source else -1,
                inferred=True,
                verification_method="test_evidence",
                extraction_confidence=0.8,
            )
        )

    if level <= 1 and not is_code and not is_research:
        constraints.append(
            CheckableConstraint(
                id="direct",
                kind="answer_directly",
                description="Answer directly. Do not call tools.",
                inferred=True,
                verification_method="draft_shape",
                extraction_confidence=0.7,
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
                source_text=source_prompt,
                source_start=0,
                source_end=len(source_prompt),
                inferred=True,
                verification_method="draft_terms",
                extraction_confidence=0.5,
            )
        )

    if is_research:
        deliverable = "Cited answer with verbatim quotes and URLs"
        next_action: NextAction = "evidence"
        evidence = ("Primary-source quotes from live pages.",)
    elif is_code:
        deliverable = "Minimal patch or code plus a validation log"
        next_action = "verify_tests" if any(item.kind == "run_tests" for item in constraints) else "none"
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
    do_not.extend(f"Do not {item.value}" for item in banned[:3])

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
                source_text=str(item.get("source_text") or ""),
                source_start=int(item.get("source_start", -1)),
                source_end=int(item.get("source_end", -1)),
                inferred=bool(item.get("inferred", False)),
                verification_method=str(item.get("verification_method") or "draft"),
                extraction_confidence=float(item.get("extraction_confidence", 1.0)),
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
