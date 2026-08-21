from pathlib import Path
from scripts.run_ablation_eval import run_ablation_study


def test_five_arm_ablation_study():
    corpus_path = Path(
        "/Users/snehgabani/.gemini/antigravity/scratch/elite-system/evals/contracts/frozen_corpus_250.json"
    )
    results = run_ablation_study(corpus_path)

    assert results["sample_size"] == 250
    metrics = results["arm_metrics"]
    assert metrics["arm5_full_elite_pass_rate"] >= metrics["arm1_host_alone_pass_rate"]

    stats = results["statistical_tests"]
    assert stats["mcnemar_statistic"] > 0
    assert stats["relative_defect_reduction"] > 0
