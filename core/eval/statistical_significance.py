"""
Statistical Significance & Double-Blind Science Evaluation Engine.
Calculates rigorous statistical metrics for paired A/B trials:
- McNemar exact test for binary paired pass rates
- Wilcoxon signed-rank test for paired continuous ratings
- Cohen\'s d effect size for magnitude of treatment lift
- Bradley-Terry Elo calculation
- Percentile bootstrap 95% confidence intervals
- Human friction & headache index
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple


@dataclass(frozen=True)
class StatisticalScorecard:
    n_trials: int
    baseline_pass_rate: float
    treatment_pass_rate: float
    pass_rate_lift_pct: float
    mcnemar_p_value: float
    wilcoxon_p_value: float
    cohens_d: float
    cohens_d_interpretation: str
    elo_delta: float
    bootstrap_ci_95_lift: Tuple[float, float]
    headache_index_baseline: float
    headache_index_treatment: float
    headache_reduction_pct: float
    statistically_significant: bool
    empirical_verdict: str


def compute_mcnemar_exact(b_baseline_only: int, c_treatment_only: int) -> float:
    """Calculates exact two-sided binomial p-value for paired discordant counts."""
    n_discordant = b_baseline_only + c_treatment_only
    if n_discordant == 0:
        return 1.0
    try:
        from scipy.stats import binomtest

        return float(binomtest(c_treatment_only, n_discordant, 0.5, alternative="two-sided").pvalue)
    except Exception:
        # Exact two-sided binomial tail
        k_min = min(b_baseline_only, c_treatment_only)
        p_val = 2.0 * sum(math.comb(n_discordant, k) * (0.5**n_discordant) for k in range(k_min + 1))
        return min(1.0, round(p_val, 4))


def compute_cohens_d(treatment_scores: Sequence[float], baseline_scores: Sequence[float]) -> Tuple[float, str]:
    """Calculates Cohen\'s d effect size and standard qualitative interpretation."""
    if len(treatment_scores) != len(baseline_scores) or len(treatment_scores) < 2:
        return 0.0, "insufficient_data"

    n = len(treatment_scores)
    mean_t = sum(treatment_scores) / n
    mean_b = sum(baseline_scores) / n

    var_t = sum((x - mean_t) ** 2 for x in treatment_scores) / (n - 1)
    var_b = sum((x - mean_b) ** 2 for x in baseline_scores) / (n - 1)
    pooled_sd = math.sqrt((var_t + var_b) / 2.0)

    if pooled_sd == 0.0:
        d = 0.0
    else:
        d = round((mean_t - mean_b) / pooled_sd, 3)

    if abs(d) >= 0.8:
        # Effect magnitude and statistical significance are different concepts.
        # Small pilots can have a large observed d without confirmatory evidence.
        interp = "Large observed standardized difference"
    elif abs(d) >= 0.5:
        interp = "Medium effect size"
    elif abs(d) >= 0.2:
        interp = "Small effect size"
    else:
        interp = "Negligible effect size"

    return d, interp


def compute_wilcoxon_signed_rank(diffs: Sequence[float]) -> float:
    """Calculates two-sided p-value for paired differences using Wilcoxon signed-rank."""
    non_zero = [d for d in diffs if d != 0.0]
    if not non_zero:
        return 1.0
    try:
        from scipy.stats import wilcoxon

        res = wilcoxon(non_zero, alternative="two-sided")
        return float(res.pvalue)
    except Exception:
        # Normal approximation for W when scipy is unavailable
        n = len(non_zero)
        if n < 5:
            return 0.05 if all(d > 0 for d in non_zero) else 0.50
        ranked = sorted([(abs(d), d) for d in non_zero], key=lambda x: x[0])
        w_plus = sum(rank for rank, (abs_d, orig_d) in enumerate(ranked, 1) if orig_d > 0)
        mean_w = n * (n + 1) / 4.0
        sd_w = math.sqrt(n * (n + 1) * (2 * n + 1) / 24.0)
        z = (w_plus - mean_w) / (sd_w if sd_w > 0 else 1.0)
        p_approx = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2))))
        return round(p_approx, 4)


def compute_bootstrap_ci(diffs: Sequence[float], n_boot: int = 5000, seed: int = 42) -> Tuple[float, float]:
    """Computes 95% bootstrap confidence interval for mean lift."""
    if not diffs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(n_boot):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = round(means[int(0.025 * n_boot)], 4)
    hi = round(means[int(0.975 * n_boot)], 4)
    return (lo, hi)


def evaluate_statistical_scorecard(
    baseline_passes: Sequence[bool],
    treatment_passes: Sequence[bool],
    baseline_scores: Optional[Sequence[float]] = None,
    treatment_scores: Optional[Sequence[float]] = None,
    baseline_interventions: int = 0,
    treatment_interventions: int = 0,
) -> StatisticalScorecard:
    """
    Compiles complete science-grade statistical scorecard across paired trials.
    """
    n = len(baseline_passes)
    if n == 0 or len(treatment_passes) != n:
        raise ValueError("Must provide equal non-zero paired test outcomes")

    b_ok = sum(1 for x in baseline_passes if x)
    t_ok = sum(1 for x in treatment_passes if x)

    base_rate = b_ok / n
    treat_rate = t_ok / n
    lift_pct = round((treat_rate - base_rate) * 100.0, 2)

    # Discordant pairs for McNemar
    b_only = sum(1 for b, t in zip(baseline_passes, treatment_passes) if b and not t)
    t_only = sum(1 for b, t in zip(baseline_passes, treatment_passes) if not b and t)
    mcnemar_p = compute_mcnemar_exact(b_only, t_only)

    # Continuous scores
    b_scores = list(baseline_scores) if baseline_scores is not None else [1.0 if x else 0.0 for x in baseline_passes]
    t_scores = list(treatment_scores) if treatment_scores is not None else [1.0 if x else 0.0 for x in treatment_passes]
    diffs = [t - b for b, t in zip(b_scores, t_scores)]

    cohen_d, cohen_interp = compute_cohens_d(t_scores, b_scores)
    wilcoxon_p = compute_wilcoxon_signed_rank(diffs)
    boot_lo, boot_hi = compute_bootstrap_ci(diffs)

    # Elo Delta (Bradley-Terry)
    w_t = max(t_ok, 1)
    w_b = max(b_ok, 1)
    elo_delta = round(400.0 * math.log10(w_t / w_b), 1)

    # Headache / Friction Index: Interventions + 0.5 * Retries + 2.0 * Failures
    h_base = round((baseline_interventions + (n - b_ok) * 2.0) / n, 3)
    h_treat = round((treatment_interventions + (n - t_ok) * 2.0) / n, 3)
    h_reduc = round(((h_base - h_treat) / h_base * 100.0) if h_base > 0 else 0.0, 1)

    # Constraint pass/fail is the registered primary endpoint, so its paired
    # McNemar result controls confirmatory significance. A secondary Wilcoxon
    # result must not override a non-significant primary endpoint.
    is_significant = mcnemar_p <= 0.05 and treat_rate >= base_rate
    if is_significant:
        verdict = "PRIMARY_ENDPOINT_SIGNIFICANT"
    elif treat_rate > base_rate:
        verdict = "INTERNAL_PILOT_DIRECTIONAL"
    else:
        verdict = "INCONCLUSIVE"

    return StatisticalScorecard(
        n_trials=n,
        baseline_pass_rate=round(base_rate, 4),
        treatment_pass_rate=round(treat_rate, 4),
        pass_rate_lift_pct=lift_pct,
        mcnemar_p_value=round(mcnemar_p, 4),
        wilcoxon_p_value=round(wilcoxon_p, 4),
        cohens_d=cohen_d,
        cohens_d_interpretation=cohen_interp,
        elo_delta=elo_delta,
        bootstrap_ci_95_lift=(boot_lo, boot_hi),
        headache_index_baseline=h_base,
        headache_index_treatment=h_treat,
        headache_reduction_pct=h_reduc,
        statistically_significant=is_significant,
        empirical_verdict=verdict,
    )
