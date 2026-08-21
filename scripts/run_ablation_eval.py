"""Five-arm ablation analysis for externally generated matched outcomes.

This module never simulates model success. Each task must contain an `outcomes`
object populated by an independent runner before inferential statistics are
computed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from core.eval.statistical_significance import compute_mcnemar_exact

ARMS = (
    "arm1_host_alone",
    "arm2_checklist",
    "arm3_contract_only",
    "arm4_verify_only",
    "arm5_full_elite",
)


def run_ablation_study(corpus_path: Path) -> Dict[str, Any]:
    data = json.loads(corpus_path.read_text(encoding="utf-8"))
    tasks = list(data.get("tasks") or [])
    observed = [
        task
        for task in tasks
        if isinstance(task.get("outcomes"), dict) and all(isinstance(task["outcomes"].get(arm), bool) for arm in ARMS)
    ]
    if not observed:
        return {
            "schema_version": "1.1.0",
            "status": "NOT_RUN",
            "corpus_size": len(tasks),
            "evaluated_pairs": 0,
            "arms": list(ARMS),
            "arm_metrics": {f"{arm}_pass_rate": None for arm in ARMS},
            "statistical_tests": None,
            "limitations": [
                "No independently generated matched arm outcomes are present.",
                "The corpus defines tasks only; it does not prove product lift.",
            ],
        }

    rates = {
        f"{arm}_pass_rate": round(sum(task["outcomes"][arm] for task in observed) / len(observed), 4) for arm in ARMS
    }
    baseline = [task["outcomes"][ARMS[0]] for task in observed]
    treatment = [task["outcomes"][ARMS[-1]] for task in observed]
    baseline_only = sum(left and not right for left, right in zip(baseline, treatment))
    treatment_only = sum(not left and right for left, right in zip(baseline, treatment))
    return {
        "schema_version": "1.1.0",
        "status": "OBSERVED",
        "corpus_size": len(tasks),
        "evaluated_pairs": len(observed),
        "arms": list(ARMS),
        "arm_metrics": rates,
        "statistical_tests": {
            "baseline_only_wins": baseline_only,
            "treatment_only_wins": treatment_only,
            "mcnemar_exact_p": compute_mcnemar_exact(baseline_only, treatment_only),
            "confirmatory": False,
        },
        "limitations": ["Confirmatory interpretation requires a preregistered powered sample and locked outcomes."],
    }


if __name__ == "__main__":
    path = Path(__file__).resolve().parent.parent / "evals/contracts/frozen_corpus_250.json"
    print(json.dumps(run_ablation_study(path), indent=2))
