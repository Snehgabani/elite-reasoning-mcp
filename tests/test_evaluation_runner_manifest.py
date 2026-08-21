from pathlib import Path
from scripts.run_evaluation import run_evaluation_manifest


def test_evaluation_runner_manifest():
    repo_root = Path(__file__).resolve().parent.parent
    manifest_path = repo_root / "evals/manifests/eval_manifest_v1.json"
    results = run_evaluation_manifest(manifest_path)

    assert results["total_tasks"] == 2
    assert results["compiled_contracts"] == 2
    assert results["exact_requirement_recall"] >= 0.90
    assert results["critical_invented_rate"] <= 0.02
