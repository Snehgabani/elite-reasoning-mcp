"""A/B Testing Framework — Statistical comparison of reasoning enhancement.

Measures whether the reasoning pipeline actually improves LLM outcomes
using rigorous statistical methods:
- Paired comparison (same prompts, with/without pipeline)
- Cohen's d effect size
- Win rate analysis
- Confidence intervals
- Statistical significance (Welch's t-test approximation)
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class ABTestResult:
    """Complete A/B test result with statistical analysis."""
    eval_name: str
    baseline_n: int
    enhanced_n: int
    baseline_mean: float
    enhanced_mean: float
    delta: float
    cohens_d: float
    effect_size: str
    win_rate: float
    confidence_interval: tuple[float, float]
    p_value_approx: float
    significant: bool
    interpretation: str
    recommendation: str


def run_ab_test(
    eval_name: str,
    baseline_scores: list[float],
    enhanced_scores: list[float],
    alpha: float = 0.05,
) -> ABTestResult:
    """Run a complete A/B test comparison.
    
    Args:
        eval_name: Name of the evaluation
        baseline_scores: Scores WITHOUT reasoning enhancement
        enhanced_scores: Scores WITH reasoning enhancement
        alpha: Significance level (default 0.05 = 95% confidence)
    """
    if not baseline_scores or not enhanced_scores:
        return ABTestResult(
            eval_name=eval_name,
            baseline_n=len(baseline_scores),
            enhanced_n=len(enhanced_scores),
            baseline_mean=0, enhanced_mean=0, delta=0,
            cohens_d=0, effect_size="insufficient_data",
            win_rate=0, confidence_interval=(0, 0),
            p_value_approx=1.0, significant=False,
            interpretation="Insufficient data for comparison.",
            recommendation="Collect at least 5 scores per variant.",
        )

    b_mean = sum(baseline_scores) / len(baseline_scores)
    e_mean = sum(enhanced_scores) / len(enhanced_scores)
    delta = e_mean - b_mean

    b_std = _stddev(baseline_scores)
    e_std = _stddev(enhanced_scores)

    # Cohen's d (pooled standard deviation)
    n_b, n_e = len(baseline_scores), len(enhanced_scores)
    pooled_std = math.sqrt(
        ((n_b - 1) * b_std**2 + (n_e - 1) * e_std**2) / (n_b + n_e - 2)
    ) if (n_b + n_e - 2) > 0 else 0.1
    pooled_std = max(pooled_std, 0.001)
    cohens_d = delta / pooled_std

    # Effect size interpretation (Cohen, 1988)
    if abs(cohens_d) < 0.2:
        effect_size = "negligible"
    elif abs(cohens_d) < 0.5:
        effect_size = "small"
    elif abs(cohens_d) < 0.8:
        effect_size = "medium"
    else:
        effect_size = "large"

    # Win rate: % of enhanced scores above baseline mean
    win_rate = sum(1 for s in enhanced_scores if s > b_mean) / n_e

    # Confidence interval for the difference (Welch's t-test approximation)
    se = math.sqrt(b_std**2 / n_b + e_std**2 / n_e) if (n_b > 0 and n_e > 0) else 0.1
    # Approximate degrees of freedom (Welch-Satterthwaite)
    if b_std > 0 and e_std > 0 and n_b > 1 and n_e > 1:
        num = (b_std**2 / n_b + e_std**2 / n_e)**2
        den = (b_std**2 / n_b)**2 / (n_b - 1) + (e_std**2 / n_e)**2 / (n_e - 1)
        df = num / den if den > 0 else n_b + n_e - 2
    else:
        df = n_b + n_e - 2
    
    # t-critical approximation (for 95% CI, df > 30: t ≈ 1.96)
    t_crit = _t_critical_approx(df, alpha)
    ci_lower = delta - t_crit * se
    ci_upper = delta + t_crit * se

    # P-value approximation
    t_stat = delta / se if se > 0 else 0
    p_value = _p_value_approx(abs(t_stat), df)

    significant = p_value < alpha

    # Interpretation
    direction = "improvement" if delta > 0 else "regression"
    if effect_size == "negligible":
        interpretation = f"Negligible difference (d={cohens_d:.3f}, p={p_value:.4f}). Reasoning enhancement shows no measurable impact."
    elif significant:
        interpretation = f"Statistically significant {direction} (d={cohens_d:.3f}, p={p_value:.4f}, {effect_size} effect). Enhancement {'helps' if delta > 0 else 'hurts'}."
    else:
        interpretation = f"{effect_size.capitalize()} effect (d={cohens_d:.3f}) but not statistically significant (p={p_value:.4f}). Need more samples."

    # Recommendation
    if significant and delta > 0 and effect_size in ("medium", "large"):
        recommendation = "STRONG EVIDENCE: Reasoning enhancement measurably improves outcomes. Deploy for this task class."
    elif significant and delta > 0:
        recommendation = "MODERATE EVIDENCE: Enhancement helps but effect is small. Deploy if latency cost is acceptable."
    elif not significant and effect_size != "negligible":
        recommendation = f"INCONCLUSIVE: Possible {effect_size} effect but insufficient data. Collect {max(10, 20 - n_b - n_e)} more samples per variant."
    elif significant and delta < 0:
        recommendation = "WARNING: Enhancement appears to HURT outcomes. Investigate and consider disabling for this task class."
    else:
        recommendation = "NO EVIDENCE: Enhancement has negligible impact. Consider removing for this task class to save latency."

    return ABTestResult(
        eval_name=eval_name,
        baseline_n=n_b,
        enhanced_n=n_e,
        baseline_mean=round(b_mean, 4),
        enhanced_mean=round(e_mean, 4),
        delta=round(delta, 4),
        cohens_d=round(cohens_d, 4),
        effect_size=effect_size,
        win_rate=round(win_rate, 4),
        confidence_interval=(round(ci_lower, 4), round(ci_upper, 4)),
        p_value_approx=round(p_value, 4),
        significant=significant,
        interpretation=interpretation,
        recommendation=recommendation,
    )


def compute_sample_size_needed(
    expected_effect: float = 0.5,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """Compute minimum sample size needed per variant.
    
    Uses standard power analysis formula for two-sample t-test.
    
    Args:
        expected_effect: Expected Cohen's d (0.2=small, 0.5=medium, 0.8=large)
        alpha: Significance level
        power: Statistical power (probability of detecting true effect)
    """
    # z-values for alpha and power
    z_alpha = 1.96 if alpha == 0.05 else 2.576  # two-tailed
    z_beta = 0.842 if power == 0.80 else 1.282  # 80% or 90% power
    
    n = 2 * ((z_alpha + z_beta) / expected_effect) ** 2
    return math.ceil(n)


# ── Statistical Helpers ──────────────────────────────────────

def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean)**2 for v in values) / (len(values) - 1))


def _t_critical_approx(df: float, alpha: float = 0.05) -> float:
    """Approximate t-critical value for two-tailed test."""
    if df >= 120:
        return 1.96 if alpha == 0.05 else 2.576
    elif df >= 60:
        return 2.00 if alpha == 0.05 else 2.66
    elif df >= 30:
        return 2.04 if alpha == 0.05 else 2.75
    elif df >= 20:
        return 2.09 if alpha == 0.05 else 2.85
    elif df >= 10:
        return 2.23 if alpha == 0.05 else 3.17
    elif df >= 5:
        return 2.57 if alpha == 0.05 else 4.03
    else:
        return 3.18 if alpha == 0.05 else 5.21


def _p_value_approx(t_stat: float, df: float) -> float:
    """Approximate two-tailed p-value from t-statistic.
    
    Uses the approximation: p ≈ 2 * (1 - Φ(|t|)) for large df,
    with correction for small df.
    """
    if df <= 0:
        return 1.0
    
    # For large df, t approaches normal
    if df >= 30:
        # Normal approximation
        z = t_stat
        p = 2 * (1 - _normal_cdf(z))
    else:
        # Rough correction for small df
        correction = 1 + (1 / (4 * df))
        z = t_stat / correction
        p = 2 * (1 - _normal_cdf(z))
    
    return max(0.0, min(1.0, p))


def _normal_cdf(z: float) -> float:
    """Approximate standard normal CDF using Abramowitz and Stegun."""
    if z < -8:
        return 0.0
    if z > 8:
        return 1.0
    
    # Abramowitz and Stegun approximation (error < 1.5e-7)
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    
    sign = 1 if z >= 0 else -1
    z = abs(z) / math.sqrt(2)
    t = 1.0 / (1.0 + p * z)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-z * z)
    
    return 0.5 * (1.0 + sign * y)
