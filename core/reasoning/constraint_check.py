"""IFEval-style checkers: a draft either meets a constraint or it does not.

No keyword 'quality scores'. Cheap models improve when the target is binary
(Zhou et al., IFEval 2023). This module never calls an LLM.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from core.reasoning.task_contract import CheckableConstraint, TaskContract, compile_task_contract


@dataclass(frozen=True)
class ConstraintResult:
    id: str
    kind: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CheckReport:
    passed: bool
    pass_rate: float
    results: tuple[ConstraintResult, ...]
    unmet: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "pass_rate": self.pass_rate,
            "results": [item.to_dict() for item in self.results],
            "unmet": list(self.unmet),
        }


_TEST_LOG_MARKERS = (
    "passed",
    "ok",
    "exit code 0",
    "exit_code=0",
    "ruff check",
    "pytest",
)
_FAKE_SUCCESS_MARKERS = (
    "proof_of_work",
    "quality_score",
    "layers_executed",
    "verified_perfect",
)
_QUOTE_RE = re.compile(r'"([^"]{12,240})"|“([^”]{12,240})”')
_URL_RE = re.compile(r"https?://[^\s)>\]]+", re.I)


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _has_terms(text: str, terms: tuple[str, ...], minimum: int = 1) -> bool:
    if not terms:
        return True
    lower = text.lower()
    hits = sum(1 for term in terms if term.lower() in lower)
    return hits >= min(minimum, len(terms))


def check_constraint(draft: str, constraint: CheckableConstraint) -> ConstraintResult:
    """Evaluate one constraint against a model draft."""
    text = draft or ""
    lower = text.lower()
    kind = constraint.kind

    if kind == "must_include":
        needed = max(1, min(2, len(constraint.terms)))
        ok = _has_terms(text, constraint.terms, minimum=needed)
        return ConstraintResult(constraint.id, kind, ok, "required terms present" if ok else "missing required terms")

    if kind == "must_not":
        ok = not _has_terms(text, constraint.terms, minimum=1) if constraint.terms else True
        if any(marker in lower for marker in _FAKE_SUCCESS_MARKERS):
            ok = False
        return ConstraintResult(
            constraint.id, kind, ok, "forbidden content absent" if ok else "forbidden content found"
        )

    if kind == "max_words":
        count = _word_count(text)
        ok = count <= max(1, constraint.value)
        return ConstraintResult(constraint.id, kind, ok, f"{count} words (cap {constraint.value})")

    if kind == "format":
        fmt = (constraint.pattern or "").lower()
        ok = True
        if fmt == "json":
            ok = bool(re.search(r"\{[\s\S]*\}", text))
        elif fmt == "patch":
            ok = "diff --git" in text or text.lstrip().startswith(("---", "+++", "@@")) or "```" in text
        elif fmt == "bullets":
            ok = bool(re.search(r"(?m)^\s*[-*]\s+\S", text))
        elif fmt == "markdown":
            ok = bool(re.search(r"^#|\*\*|```", text, re.M))
        return ConstraintResult(constraint.id, kind, ok, f"format={fmt}")

    if kind == "cite_quotes":
        quotes = _QUOTE_RE.findall(text)
        urls = _URL_RE.findall(text)
        ok = bool(quotes) and bool(urls)
        return ConstraintResult(
            constraint.id,
            kind,
            ok,
            f"{len(urls)} urls, {len(quotes)} quotes" if ok else "need verbatim quote AND url",
        )

    if kind == "run_tests":
        ok = any(marker in lower for marker in _TEST_LOG_MARKERS) and "failed" not in lower[-200:]
        return ConstraintResult(constraint.id, kind, ok, "validation log present" if ok else "no passing test/lint log")

    if kind == "scope_files":
        mentioned = set(re.findall(r"[\w./-]+\.(?:py|ts|js|tsx|jsx|md|toml|yml|yaml|json)", text))
        allowed = {item.lower() for item in constraint.terms}
        extras = {item for item in mentioned if item.lower() not in allowed}
        # Drafts that never mention files cannot be failed on scope alone.
        ok = not extras
        return ConstraintResult(constraint.id, kind, ok, "in scope" if ok else f"out of scope: {sorted(extras)[:5]}")

    if kind == "answer_directly":
        ok = _word_count(text) <= 400 and "elite_prepare" not in lower
        return ConstraintResult(constraint.id, kind, ok, "direct answer" if ok else "over-tooled or too long")

    return ConstraintResult(constraint.id, kind, False, f"unknown constraint kind `{kind}`")


def check_draft(draft: str, contract: TaskContract | None = None, prompt: str = "") -> CheckReport:
    """Check a draft against a contract (compiled from prompt if needed)."""
    if contract is None:
        if not prompt.strip():
            raise ValueError("contract or prompt is required")
        contract = compile_task_contract(prompt)
    results = tuple(check_constraint(draft, item) for item in contract.constraints)
    passed_count = sum(1 for item in results if item.passed)
    total = max(1, len(results))
    unmet = tuple(f"{item.id}: {item.detail}" for item in results if not item.passed)
    return CheckReport(
        passed=not unmet,
        pass_rate=round(passed_count / total, 3),
        results=results,
        unmet=unmet,
    )
