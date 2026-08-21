#!/usr/bin/env python3
"""
Science-Grade Double-Blind Randomized Controlled Trial (RCT) Evaluation Harness.
Provides unbiased, non-contaminated paired evaluation comparing baseline Small Language Models (SLMs)
against SLMs augmented with Elite Cognitive Exoskeleton Scaffolding.

Zero-Hype & Integrity Invariants:
1. No in-process `exec()` calls: uses AST grammar evaluation and isolated subprocess/contract checkers.
2. No hardcoded or rule-based scores (e.g. 0.98 or max(0.95, ...)).
3. True cryptographically secure position-swapping with independent dual-pass judging.
4. Reports exact McNemar tests, Wilcoxon p-values, Cohen's d effect sizes, and bootstrap 95% CIs.
5. Emits pre-registered ship/hold/reject verdicts.
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
    print(f"🔬 RUNNING DOUBLE-BLIND RCT EVALUATION HARNESS (Split: {split})")
    print("================================================================================")

    runner = DoubleBlindRCTRunner(seed=42)
    results = runner.run_suite(split=split)
    report_md = runner.generate_markdown_report(results)

    out_file = Path(output_path)
    out_file.write_text(report_md, encoding="utf-8")

    sc = results["scorecard"]
    print("\n✅ Evaluation Complete:")
    print(f"  - Total Paired Trials:        {sc['n_trials']}")
    print(f"  - Baseline Pass Rate:         {sc['baseline_pass_rate'] * 100:.1f}%")
    print(f"  - Treatment Pass Rate:        {sc['treatment_pass_rate'] * 100:.1f}%")
    print(f"  - Measured Lift:              +{sc['pass_rate_lift_pct']:.1f}%")
    print(f"  - McNemar p-value:            {sc['mcnemar_p_value']:.4f}")
    print(f"  - Wilcoxon Signed-Rank p:     {sc['wilcoxon_p_value']:.4f}")
    print(f"  - Cohen's d Effect Size:      {sc['cohens_d']:.3f} ({sc['cohens_d_interpretation']})")
    print(f"  - Bradley-Terry Delta Elo:    +{sc['elo_delta']:.1f}")
    print(f"  - Bootstrap 95% CI on Lift:   [{sc['bootstrap_ci_95_lift'][0]:.3f}, {sc['bootstrap_ci_95_lift'][1]:.3f}]")
    print(
        f"  - Headache / Friction Index:  {sc['headache_index_baseline']:.2f} -> {sc['headache_index_treatment']:.2f} (-{sc['headache_reduction_pct']:.1f}%)"
    )
    print(f"  - Empirical Scientific Verdict: {sc['empirical_verdict']}")
    print(f"\n📄 Full report written to: {out_file.resolve()}\n")


def main():
    parser = argparse.ArgumentParser(description="Double-Blind Evaluation Runner")
    parser.add_argument("--split", choices=["dev", "holdout", "all"], default="all", help="Dataset split to evaluate")
    parser.add_argument("--output", type=str, default="BENCHMARK_REPORT.md", help="Output file path")
    args = parser.parse_args()

    run_evaluation(split=args.split, output_path=args.output)


if __name__ == "__main__":
    main()
