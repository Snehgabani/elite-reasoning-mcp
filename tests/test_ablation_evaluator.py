import json
from pathlib import Path

from scripts.run_ablation_eval import ARMS, run_ablation_study


def test_five_arm_corpus_does_not_fabricate_unobserved_model_results():
    repo_root = Path(__file__).resolve().parent.parent
    corpus_path = repo_root / "evals/contracts/frozen_corpus_250.json"
    results = run_ablation_study(corpus_path)

    assert results["corpus_size"] == 250
    assert results["status"] == "NOT_RUN"
    assert results["evaluated_pairs"] == 0
    assert results["statistical_tests"] is None
    assert all(value is None for value in results["arm_metrics"].values())


def test_five_arm_analysis_uses_only_supplied_matched_outcomes(tmp_path):
    tasks = []
    for index in range(8):
        outcomes = {arm: False for arm in ARMS}
        outcomes["arm5_full_elite"] = index < 6
        tasks.append({"id": f"t{index}", "instruction": "fixture", "outcomes": outcomes})
    path = tmp_path / "observed.json"
    path.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")

    results = run_ablation_study(path)
    assert results["status"] == "OBSERVED"
    assert results["evaluated_pairs"] == 8
    assert results["arm_metrics"]["arm1_host_alone_pass_rate"] == 0.0
    assert results["arm_metrics"]["arm5_full_elite_pass_rate"] == 0.75
    assert results["statistical_tests"]["treatment_only_wins"] == 6
    assert results["statistical_tests"]["mcnemar_exact_p"] == 0.03125
    assert results["statistical_tests"]["confirmatory"] is False
