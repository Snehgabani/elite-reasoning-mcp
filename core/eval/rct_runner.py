"""Internal paired-fixture evaluation runner.

The bundled candidates are hand-authored protocol fixtures, not outputs from a
live randomized model experiment. This runner exercises deterministic scoring,
position assignment, and report generation. It must not be presented as an RCT
or as evidence of broad model improvement.
"""

from __future__ import annotations

import argparse
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from core.eval.blind_protocol import BLIND_CASES, BlindCase, score_constraint_case
from core.eval.statistical_significance import evaluate_statistical_scorecard
from core.evidence.fact_grounder import FActScoreGrounder
from core.evidence.grounded_search import EvidenceQuote, GroundedEvidence


@dataclass(frozen=True)
class PairedTrialResult:
    case_id: str
    split: str
    slice_type: str
    prompt: str
    is_order_swapped: bool
    baseline_passed: bool
    treatment_passed: bool
    baseline_score: float
    treatment_score: float
    baseline_fact_score: float
    treatment_fact_score: float
    tokens_baseline: int
    tokens_treatment: int


class DoubleBlindRCTRunner:
    """Score bundled paired fixtures with reproducible position assignment.

    The compatibility class name is retained for existing imports. Candidate
    generation and evaluator blinding are outside this implementation.
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)
        self.fact_grounder = FActScoreGrounder(min_fact_score_threshold=0.80)

    def run_trial_case(self, case: BlindCase) -> PairedTrialResult:
        """Executes a single double-blind paired trial with randomized presentation."""
        swap = bool(self.rng.randint(0, 1))

        # Evaluate constraints deterministically
        b_res = score_constraint_case(case.prompt, case.baseline_draft)
        t_res = score_constraint_case(case.prompt, case.treatment_draft)

        b_pass = bool(b_res["passed"])
        t_pass = bool(t_res["passed"])
        b_score = float(b_res["pass_rate"])
        t_score = float(t_res["pass_rate"])

        # Grounding checks on quotes
        evidence = GroundedEvidence(
            query=case.prompt,
            quotes=(
                EvidenceQuote(
                    url="https://example.com/mcp-tax",
                    title="MCP Token Overhead",
                    quote="tool definitions sitting in context permanently",
                ),
                EvidenceQuote(
                    url="https://example.com/tokens",
                    title="Token Dynamics",
                    quote="injected into the model context on every request",
                ),
            ),
            sources_fetched=2,
            sources_readable=2,
            degraded=False,
            uncertain=(),
            retrieved_at="2026-08-21T00:00:00Z",
        )

        b_ground = self.fact_grounder.evaluate_grounding(case.baseline_draft, evidence)
        t_ground = self.fact_grounder.evaluate_grounding(case.treatment_draft, evidence)

        return PairedTrialResult(
            case_id=case.case_id,
            split=case.split,
            slice_type=case.slice,
            prompt=case.prompt,
            is_order_swapped=swap,
            baseline_passed=b_pass,
            treatment_passed=t_pass,
            baseline_score=b_score,
            treatment_score=t_score,
            baseline_fact_score=b_ground.fact_score,
            treatment_fact_score=t_ground.fact_score,
            tokens_baseline=case.tokens_baseline,
            tokens_treatment=case.tokens_treatment,
        )

    def run_suite(self, split: str = "all") -> Dict[str, Any]:
        """Runs the complete RCT benchmark suite on the selected split."""
        target_cases = [c for c in BLIND_CASES if split == "all" or c.split == split]

        trials: List[PairedTrialResult] = []
        for c in target_cases:
            res = self.run_trial_case(c)
            trials.append(res)

        b_passes = [t.baseline_passed for t in trials]
        t_passes = [t.treatment_passed for t in trials]
        b_scores = [t.baseline_score for t in trials]
        t_scores = [t.treatment_score for t in trials]

        scorecard = evaluate_statistical_scorecard(
            baseline_passes=b_passes,
            treatment_passes=t_passes,
            baseline_scores=b_scores,
            treatment_scores=t_scores,
            baseline_interventions=len([t for t in trials if not t.baseline_passed]),
            treatment_interventions=len([t for t in trials if not t.treatment_passed]),
        )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "split": split,
            "scorecard": asdict(scorecard),
            "trials": [asdict(t) for t in trials],
        }

    def generate_markdown_report(self, results: Dict[str, Any]) -> str:
        """Generate an explicitly limited internal-fixture pilot report."""
        sc = results["scorecard"]
        trials = results["trials"]
        primary_label = (
            "significant at alpha=0.05" if sc["statistically_significant"] else "not significant at alpha=0.05"
        )

        lines = [
            "# Internal Fixture Pilot Report",
            "",
            "> **Protocol smoke test—not a randomized controlled trial.** The baseline and treatment drafts are hand-authored fixtures bundled with the repository. This report validates scoring behavior; it does not estimate improvement for live models or real coding tasks.",
            "",
            f"**Execution timestamp:** `{results['timestamp']}`",
            f"**Evaluation split:** `{results['split']}` ({sc['n_trials']} paired fixtures)",
            f"**Primary-endpoint interpretation:** **{primary_label}**",
            f"**Internal verdict:** `{sc['empirical_verdict']}`",
            "",
            "## Observed fixture results",
            "",
            "| Metric | Baseline fixtures | Treatment fixtures | Observed difference / result | Interpretation |",
            "|:---|---:|---:|---:|:---|",
            f"| All-constraint pass rate | {sc['baseline_pass_rate'] * 100:.1f}% | {sc['treatment_pass_rate'] * 100:.1f}% | {sc['pass_rate_lift_pct']:+.1f} percentage points | Descriptive, n={sc['n_trials']} |",
            f"| Exact McNemar primary test | — | — | p={sc['mcnemar_p_value']:.4f} | {primary_label} |",
            f"| Wilcoxon score comparison | — | — | p={sc['wilcoxon_p_value']:.4f} | Exploratory secondary metric |",
            f"| Standardized score difference | — | — | d={sc['cohens_d']:.3f} | {sc['cohens_d_interpretation']}; not independent proof of significance |",
            f"| Bootstrap interval for mean score difference | — | — | [{sc['bootstrap_ci_95_lift'][0]:.3f}, {sc['bootstrap_ci_95_lift'][1]:.3f}] | Fixture uncertainty only; not population generalization |",
            "",
            "## Paired fixture breakdown",
            "",
            "| Case ID | Split | Slice | Display order swapped? | Baseline | Treatment | Score difference |",
            "|:---|:---|:---|:---|:---|:---|---:|",
        ]

        for trial in trials:
            baseline = "Pass" if trial["baseline_passed"] else "Fail"
            treatment = "Pass" if trial["treatment_passed"] else "Fail"
            swapped = "Yes" if trial["is_order_swapped"] else "No"
            difference = trial["treatment_score"] - trial["baseline_score"]
            lines.append(
                f"| `{trial['case_id']}` | `{trial['split']}` | `{trial['slice_type']}` | {swapped} | {baseline} | {treatment} | {difference:+.2f} |"
            )

        lines.extend(
            [
                "",
                "## Limitations",
                "",
                "- Candidate drafts are hand-authored fixtures; no host model generated either arm under randomized assignment.",
                "- Position assignment is randomized, but the deterministic constraint scorer does not inspect presentation order; this is not evaluator blinding.",
                "- Seven cases are insufficient for broad model, repository, cost, safety, or product-effect claims.",
                "- Exact quote occurrence checks do not prove source authority or full claim entailment.",
                "- The exact McNemar test is the registered primary binary endpoint. Secondary score statistics do not override it.",
                "",
                "## Appropriate use",
                "",
                "Use this suite as a release smoke test for the evaluation protocol. A confirmatory product claim requires independently generated candidates, equal budgets, a frozen larger task set, pre-registration, and external replication.",
            ]
        )
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Internal paired-fixture evaluation runner")
    parser.add_argument("--split", choices=["dev", "holdout", "all"], default="all", help="Dataset split to evaluate")
    parser.add_argument("--output", type=str, default="BENCHMARK_REPORT.md", help="Output report file")
    args = parser.parse_args()

    runner = DoubleBlindRCTRunner()
    results = runner.run_suite(split=args.split)
    report = runner.generate_markdown_report(results)

    out_path = Path(args.output)
    out_path.write_text(report, encoding="utf-8")
    print(f"Generated internal fixture pilot report at {out_path.resolve()}")
    print(f"Internal verdict: {results['scorecard']['empirical_verdict']}")
    print(
        f"Pass Rate: {results['scorecard']['baseline_pass_rate'] * 100:.1f}% -> {results['scorecard']['treatment_pass_rate'] * 100:.1f}% (+{results['scorecard']['pass_rate_lift_pct']:.1f}%)"
    )
    print(f"Cohen's d: {results['scorecard']['cohens_d']} ({results['scorecard']['cohens_d_interpretation']})")


if __name__ == "__main__":
    main()
