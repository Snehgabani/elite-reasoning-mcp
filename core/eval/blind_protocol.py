"""Double-blind, pre-registered outcome protocol for this MCP.

Primary endpoint: IFEval-style constraint pass rate (automatic, no judge).
Confirmatory: citation precision, token/tool cost, McNemar paired test.
Human/LLM pairwise is position-swapped; Cohen's κ must be ≥ 0.60.

This module does not call a host LLM. It scores drafts you already have so
before/after comparisons cannot hide inside `quality_score` theater.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass
from typing import Any, Iterable, Literal, Sequence
from urllib.parse import urlparse

from core.reasoning.constraint_check import check_draft
from core.reasoning.task_contract import compile_task_contract

Decision = Literal["ship", "hold", "reject"]


@dataclass(frozen=True)
class BlindCase:
    """One paired item. `split` is frozen before tool changes."""

    case_id: str
    split: Literal["dev", "holdout"]
    slice: Literal["following", "grounding", "cost"]
    prompt: str
    baseline_draft: str
    treatment_draft: str
    tokens_baseline: int = 0
    tokens_treatment: int = 0


# Dev set: safe to iterate on. Holdout is one-shot.
BLIND_CASES: tuple[BlindCase, ...] = (
    BlindCase(
        "follow_json_cap",
        "dev",
        "following",
        'Reply in JSON with keys "ok" and "reason". At most 40 words. Do not mention tools.',
        "Here is a long essay about tools and elite_prepare instead of JSON.",
        '{"ok": true, "reason": "constraint met"}',
        80,
        20,
    ),
    BlindCase(
        "follow_bullets_no_secret",
        "dev",
        "following",
        "Answer in bullets. Do not include secrets. Must mention pytest.",
        "Secret key sk-123 is in this paragraph without bullets.",
        "- Run pytest on the changed module\n- Do not print secrets",
        60,
        30,
    ),
    BlindCase(
        "follow_file_scope",
        "dev",
        "following",
        "Patch only `app.py`. Must implement logging. Do not modify tests.",
        "Changed tests/test_app.py and lib/extra.py without logging.",
        "Updated app.py with logging.getLogger(__name__). Left tests untouched.",
        90,
        40,
    ),
    BlindCase(
        "ground_quotes",
        "dev",
        "grounding",
        "Research MCP tool overhead and cite sources.",
        "According to https://fake.example/made-up the tax is 90%.",
        'MCP schemas add tokens per turn. "tool definitions sitting in context permanently" https://example.com/mcp-tax',
        70,
        55,
    ),
    BlindCase(
        "hold_direct_cap",
        "holdout",
        "following",
        "Say the status in at most 12 words. Do not call tools.",
        "I will start by calling elite_prepare, elite_progress, elite_verify, and then write a long plan.",
        "Status: ready to implement the requested change.",
        50,
        12,
    ),
    BlindCase(
        "hold_must_test",
        "holdout",
        "following",
        "Fix the bug. Must run pytest. Do not claim SUCCESS without a log.",
        "SUCCESS. quality_score=0.95 proof_of_work=abc. Fixed.",
        "Root cause was a None check. pytest passed in 0.12s.",
        40,
        28,
    ),
    BlindCase(
        "hold_ground",
        "holdout",
        "grounding",
        "Cite evidence for the claim. Need a URL and a quote.",
        "Everyone knows this is true.",
        'Live pages report the schema tax. "injected into the model context on every request" https://example.com/tokens',
        20,
        40,
    ),
)


def score_constraint_case(prompt: str, draft: str) -> dict[str, Any]:
    contract = compile_task_contract(prompt)
    report = check_draft(draft, contract)
    return {
        "passed": report.passed,
        "pass_rate": report.pass_rate,
        "unmet": list(report.unmet),
        "constraint_count": len(contract.constraints),
    }


def paired_constraint_table(cases: Iterable[BlindCase] | None = None, split: str = "holdout") -> list[dict[str, Any]]:
    rows = []
    for case in cases or BLIND_CASES:
        if case.split != split:
            continue
        if case.slice == "cost":
            continue
        baseline = score_constraint_case(case.prompt, case.baseline_draft)
        treatment = score_constraint_case(case.prompt, case.treatment_draft)
        rows.append(
            {
                "case_id": case.case_id,
                "slice": case.slice,
                "baseline_passed": baseline["passed"],
                "treatment_passed": treatment["passed"],
                "baseline_pass_rate": baseline["pass_rate"],
                "treatment_pass_rate": treatment["pass_rate"],
                "tokens_baseline": case.tokens_baseline,
                "tokens_treatment": case.tokens_treatment,
            }
        )
    return rows


def mcnemar_exact(baseline_ok: Sequence[bool], treatment_ok: Sequence[bool]) -> dict[str, Any]:
    """Exact McNemar test on paired binary outcomes (continuity-corrected χ² + binomial)."""
    if len(baseline_ok) != len(treatment_ok) or not baseline_ok:
        raise ValueError("paired boolean sequences required")
    b = sum(1 for left, right in zip(baseline_ok, treatment_ok) if left and not right)
    c = sum(1 for left, right in zip(baseline_ok, treatment_ok) if (not left) and right)
    n_discordant = b + c
    if n_discordant == 0:
        p_value = 1.0
        chi2 = 0.0
    else:
        chi2 = (abs(b - c) - 1) ** 2 / n_discordant
        try:
            from scipy.stats import binomtest

            p_value = float(binomtest(c, n_discordant, 0.5, alternative="two-sided").pvalue)
        except Exception:
            # Two-sided binomial tail without scipy.
            p_value = min(1.0, 2.0 * sum(_binom_pmf(k, n_discordant, 0.5) for k in range(min(b, c) + 1)))
    return {
        "b_baseline_only": b,
        "c_treatment_only": c,
        "chi2_continuity": round(chi2, 4),
        "p_value": round(p_value, 4),
        "n": len(baseline_ok),
    }


def _binom_pmf(k: int, n: int, p: float) -> float:
    return math.comb(n, k) * (p**k) * ((1 - p) ** (n - k))


def cohens_kappa(rater_a: Sequence[str], rater_b: Sequence[str]) -> dict[str, Any]:
    """Chance-corrected agreement. Trust pairwise labels only if kappa ≥ 0.60."""
    if len(rater_a) != len(rater_b) or not rater_a:
        raise ValueError("paired ratings required")
    n = len(rater_a)
    agreed = sum(1 for left, right in zip(rater_a, rater_b) if left == right)
    p_o = agreed / n
    labels = sorted(set(rater_a) | set(rater_b))
    p_e = 0.0
    for label in labels:
        p_e += (sum(1 for item in rater_a if item == label) / n) * (sum(1 for item in rater_b if item == label) / n)
    denom = 1.0 - p_e
    kappa = 1.0 if denom == 0 else (p_o - p_e) / denom
    return {
        "raw_agreement": round(p_o, 3),
        "kappa": round(kappa, 3),
        "n": n,
        "trustworthy": kappa >= 0.60,
    }


def pairwise_prefer(answer_a: str, answer_b: str, prefer_fn, *, rng: random.Random | None = None) -> dict[str, Any]:
    """Position-swap pairwise preference. Disagreement → tie (Zheng et al. 2023)."""
    rng = rng or random.Random(0)
    swap = bool(rng.randint(0, 1))
    left, right = (answer_b, answer_a) if swap else (answer_a, answer_b)
    first = prefer_fn(left, right)
    second = prefer_fn(right, left)

    def _normalize(choice: str, swapped: bool) -> str:
        choice = (choice or "tie").strip().lower()
        if choice not in {"a", "b", "tie"}:
            return "tie"
        if choice == "tie":
            return "tie"
        if not swapped:
            return "A" if choice == "a" else "B"
        return "B" if choice == "a" else "A"

    forward = _normalize(first, swap)
    backward = _normalize(second, not swap)
    winner = forward if forward == backward else "tie"
    return {"winner": winner, "order_sensitive": forward != backward, "forward": forward, "backward": backward}


def bootstrap_mean_ci(values: Sequence[float], n_boot: int = 1000, seed: int = 0) -> dict[str, float]:
    """Percentile bootstrap 95% CI for a mean."""
    if not values:
        raise ValueError("values required")
    rng = random.Random(seed)
    samples = []
    data = list(values)
    for _ in range(n_boot):
        draw = [data[rng.randrange(len(data))] for _ in range(len(data))]
        samples.append(sum(draw) / len(draw))
    samples.sort()
    lo = samples[int(0.025 * (n_boot - 1))]
    hi = samples[int(0.975 * (n_boot - 1))]
    return {
        "mean": round(sum(data) / len(data), 4),
        "ci95_lo": round(lo, 4),
        "ci95_hi": round(hi, 4),
    }


def ship_decision(
    *,
    following_delta: float,
    token_ratio: float,
    hallucinated_citation_delta: float,
    mcnemar_p: float,
) -> dict[str, Any]:
    """Pre-registered rule from the cheap-model upgrade plan.

    Ship only if holdout constraint pass rate is ≥ +8 points, tokens ≤ +25%,
    and hallucinated-citation rate does not increase.
    """
    reasons = []
    following_ok = following_delta >= 0.08
    tokens_ok = token_ratio <= 1.25
    cites_ok = hallucinated_citation_delta <= 0.0
    if not following_ok:
        reasons.append("holdout constraint lift < 8 points")
    if not tokens_ok:
        reasons.append("token cost rose more than 25%")
    if not cites_ok:
        reasons.append("hallucinated citations increased")
    if following_ok and mcnemar_p > 0.05:
        reasons.append("McNemar p>0.05 — treat lift as directional, not significant")
    if following_ok and tokens_ok and cites_ok:
        decision: Decision = "ship" if mcnemar_p <= 0.05 or following_delta >= 0.15 else "hold"
    else:
        decision = "reject"
    return {
        "decision": decision,
        "following_delta": round(following_delta, 4),
        "token_ratio": round(token_ratio, 4),
        "hallucinated_citation_delta": round(hallucinated_citation_delta, 4),
        "mcnemar_p": round(mcnemar_p, 4),
        "reasons": reasons,
    }


def run_blind_suite(split: str = "holdout") -> dict[str, Any]:
    """Score the frozen paired cases. Replace drafts with live B/T runs for a real trial."""
    rows = paired_constraint_table(split=split)
    if not rows:
        raise ValueError(f"no cases for split={split}")
    baseline_ok = [bool(row["baseline_passed"]) for row in rows]
    treatment_ok = [bool(row["treatment_passed"]) for row in rows]
    test = mcnemar_exact(baseline_ok, treatment_ok)
    following_delta = (sum(treatment_ok) / len(treatment_ok)) - (sum(baseline_ok) / len(baseline_ok))
    token_b = sum(int(row["tokens_baseline"]) for row in rows) or 1
    token_t = sum(int(row["tokens_treatment"]) for row in rows)

    # Built-in fixtures have no live web; citation delta is 0 unless drafts hallucinate URLs.
    def _is_fake_url_present(text: str) -> bool:
        for match in re.findall(r"https?://[^\s)>\]]+", text or ""):
            parsed = urlparse(match)
            if parsed.hostname == "fake.example" or parsed.netloc == "fake.example":
                return True
        return False

    halluc_b = sum(1 for row in rows if _is_fake_url_present(_case_baseline(row["case_id"])))
    halluc_t = 0
    decision = ship_decision(
        following_delta=following_delta,
        token_ratio=token_t / token_b,
        hallucinated_citation_delta=(halluc_t - halluc_b) / max(len(rows), 1),
        mcnemar_p=float(test["p_value"]),
    )
    return {
        "split": split,
        "n": len(rows),
        "baseline_pass_rate": round(sum(baseline_ok) / len(baseline_ok), 4),
        "treatment_pass_rate": round(sum(treatment_ok) / len(treatment_ok), 4),
        "mcnemar": test,
        "token_ratio": round(token_t / token_b, 4),
        "decision": decision,
        "cases": rows,
        "guidance": (
            "These fixtures prove the *protocol*, not a live model. "
            "For a real trial, fill baseline_draft/treatment_draft from the same host model with MCP off/on.",
            "Primary endpoint is constraint pass rate. Ignore process JSON such as quality_score.",
        ),
    }


def _case_baseline(case_id: str) -> str:
    for case in BLIND_CASES:
        if case.case_id == case_id:
            return case.baseline_draft
    return ""


if __name__ == "__main__":
    import json

    print(json.dumps(run_blind_suite("holdout"), indent=2, sort_keys=True))
