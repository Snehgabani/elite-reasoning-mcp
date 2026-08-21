import pytest
from core.eval.statistical_significance import (
    compute_cohens_d,
    compute_mcnemar_exact,
    compute_wilcoxon_signed_rank,
    evaluate_statistical_scorecard,
)
from core.eval.rct_runner import DoubleBlindRCTRunner


def test_statistical_significance_math():
    # Test McNemar
    p_val = compute_mcnemar_exact(b_baseline_only=0, c_treatment_only=10)
    assert p_val <= 0.05

    # Test Cohen's d with N=8 samples
    treat = [1.0, 1.0, 1.0, 1.0, 0.9, 1.0, 0.95, 1.0]
    base = [0.2, 0.3, 0.1, 0.4, 0.2, 0.1, 0.3, 0.2]
    d, interp = compute_cohens_d(treat, base)
    assert d >= 0.8
    assert "Large" in interp

    # Test Wilcoxon
    diffs = [t - b for t, b in zip(treat, base)]
    w_p = compute_wilcoxon_signed_rank(diffs)
    assert w_p <= 0.05


def test_rct_runner_execution_and_anonymization():
    runner = DoubleBlindRCTRunner(seed=123)
    results = runner.run_suite(split="all")

    assert "scorecard" in results
    assert "trials" in results
    sc = results["scorecard"]
    assert sc["n_trials"] >= 7
    assert sc["treatment_pass_rate"] > sc["baseline_pass_rate"]
    assert sc["statistically_significant"] is True
    assert sc["cohens_d"] >= 0.8

    # Verify report formatting
    report = runner.generate_markdown_report(results)
    assert "Double-Blind Randomized Controlled Trial" in report
    assert "Executive Statistical Scorecard" in report
    assert "Cohen" in report
