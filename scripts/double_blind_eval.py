#!/usr/bin/env python3
"""Run the repository's internal paired-fixture evaluation.

The bundled baseline and treatment drafts are hand-authored smoke fixtures.
This command validates deterministic scoring and report generation; it is not a
live-model experiment or a randomized controlled trial.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.eval.rct_runner import DoubleBlindRCTRunner


def run_evaluation(split: str = "all", output_path: str = "BENCHMARK_REPORT.md"):
    print("================================================================================")
    print(f"RUNNING INTERNAL PAIRED-FIXTURE PILOT (split: {split})")
    print("Protocol smoke test only; candidates are bundled hand-authored fixtures.")
    print("================================================================================")

    runner = DoubleBlindRCTRunner(seed=42)
    results = runner.run_suite(split=split)
    report_md = runner.generate_markdown_report(results)

    out_file = Path(output_path)
    out_file.write_text(report_md, encoding="utf-8")

    sc = results["scorecard"]
    print("\nInternal fixture pilot complete:")
    print(f"  - Total Paired Trials:        {sc['n_trials']}")
    print(f"  - Baseline Pass Rate:         {sc['baseline_pass_rate'] * 100:.1f}%")
    print(f"  - Treatment Pass Rate:        {sc['treatment_pass_rate'] * 100:.1f}%")
    print(f"  - Observed difference:        +{sc['pass_rate_lift_pct']:.1f} percentage points")
    print(f"  - Primary McNemar p-value:    {sc['mcnemar_p_value']:.4f}")
    print(f"  - Internal pilot verdict:     {sc['empirical_verdict']}")
    print(f"  - Primary endpoint significant: {sc['statistically_significant']}")
    print(f"\nReport written to: {out_file.resolve()}\n")


def main():
    parser = argparse.ArgumentParser(description="Internal paired-fixture evaluation runner")
    parser.add_argument("--split", choices=["dev", "holdout", "all"], default="all", help="Dataset split to evaluate")
    parser.add_argument("--output", type=str, default="BENCHMARK_REPORT.md", help="Output file path")
    args = parser.parse_args()

    run_evaluation(split=args.split, output_path=args.output)


if __name__ == "__main__":
    main()
