from core.eval.blind_protocol import (
    cohens_kappa,
    mcnemar_exact,
    paired_bootstrap_delta_ci,
    pairwise_prefer,
    position_bias_report,
    run_blind_suite,
    ship_decision,
    validate_trial_manifest,
)


def test_holdout_suite_prefers_treatment_fixtures_and_returns_decision_rule():
    report = run_blind_suite("holdout")

    assert report["n"] >= 2
    assert report["treatment_pass_rate"] > report["baseline_pass_rate"]
    assert report["decision"]["decision"] in {"ship", "hold", "reject"}
    assert report["mcnemar"]["c_treatment_only"] >= report["mcnemar"]["b_baseline_only"]


def test_mcnemar_and_kappa_and_position_swap():
    test = mcnemar_exact([True, False, False, True], [True, True, True, True])
    assert test["c_treatment_only"] == 2
    assert 0.0 <= test["p_value"] <= 1.0

    agreement = cohens_kappa(["A", "B", "A", "tie"], ["A", "B", "A", "A"])
    assert agreement["raw_agreement"] == 0.75
    assert "kappa" in agreement

    def prefer_longer(left: str, right: str) -> str:
        if len(left) == len(right):
            return "tie"
        return "a" if len(left) > len(right) else "b"

    swapped = pairwise_prefer("short", "much longer answer", prefer_longer)
    assert swapped["winner"] in {"A", "B", "tie"}


def test_position_bias_report_requires_same_candidate_after_swap():
    report = position_bias_report(["A", "B", "A", "tie"], ["A", "B", "B", "tie"])
    assert report["n"] == 4
    assert report["conflicts"] == 1
    assert report["swap_consistency"] == 0.75
    assert report["reliable_winner_rate"] == 0.5


def test_paired_bootstrap_resamples_differences_and_is_reproducible():
    report = paired_bootstrap_delta_ci([0.2, 0.4, 0.6], [0.4, 0.5, 0.9], n_boot=250, seed=7)
    assert report["mean_delta"] == 0.2
    assert report["ci95_lo"] <= report["mean_delta"] <= report["ci95_hi"]
    assert report == paired_bootstrap_delta_ci([0.2, 0.4, 0.6], [0.4, 0.5, 0.9], n_boot=250, seed=7)


def test_trial_manifest_fails_closed_for_small_hand_authored_study():
    manifest = {
        "study_id": "demo",
        "seed": "seed-1",
        "holdout_locked": True,
        "objective_oracles": ["pytest"],
        "cases": [{"case_id": "x", "source": "hand_authored", "baseline_output_hash": "a", "treatment_output_hash": "b"}],
    }
    report = validate_trial_manifest(manifest)
    assert report["valid"] is False
    assert "cases<30" in report["errors"]
    assert "hand_authored_or_fixed_score_case" in report["errors"]


def test_ship_rule_rejects_token_blowups_even_with_quality_lift():
    rejected = ship_decision(
        following_delta=0.20,
        token_ratio=2.0,
        hallucinated_citation_delta=0.0,
        mcnemar_p=0.01,
    )
    assert rejected["decision"] == "reject"
    shipped = ship_decision(
        following_delta=0.20,
        token_ratio=1.1,
        hallucinated_citation_delta=0.0,
        mcnemar_p=0.01,
    )
    assert shipped["decision"] == "ship"
