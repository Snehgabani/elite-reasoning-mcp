from core.eval.blind_protocol import (
    cohens_kappa,
    mcnemar_exact,
    pairwise_prefer,
    run_blind_suite,
    ship_decision,
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
