from core.eval.outcome_runner import (
    SMOKE_FIXTURES,
    elite_eval_suite_markdown,
    evaluate_candidate_output,
    extract_json_from_markdown,
    run_elite_eval_suite,
)
from core.eval.research_benchmarks import ELITE_SCORECARD


def test_evaluate_candidate_output_scores_strong_output_above_weak_output():
    strong = evaluate_candidate_output(
        "Implemented the fix, ran pytest and ruff, validation passed, documented risk, fallback, ROI, evidence, and confidence.",
        "Fix a repo bug with validation",
        validation_passed=True,
        tool_calls=4,
        evidence_sources=2,
        confidence=0.85,
        outcome_correct=True,
    )
    weak = evaluate_candidate_output(
        "Maybe fixed it.",
        "Fix a repo bug with validation",
        validation_passed=False,
        tool_calls=14,
        evidence_sources=0,
        confidence=0.95,
        outcome_correct=False,
    )

    assert strong.total_score > weak.total_score
    assert strong.passed is True
    assert weak.passed is False


def test_eval_suite_runs_smoke_fixtures_against_scorecard_dimensions():
    report = run_elite_eval_suite("smoke")
    scorecard_names = tuple(dimension.name for dimension in ELITE_SCORECARD)

    assert report["scope"] == "smoke"
    assert report["passed"] is True
    assert report["aggregate_score"] >= 0.74
    assert report["scorecard_dimensions"] == scorecard_names
    assert len(report["cases"]) == len(SMOKE_FIXTURES)
    assert all(case["meets_expected_min_score"] for case in report["cases"])


def test_eval_suite_markdown_round_trips_json_report():
    rendered = elite_eval_suite_markdown("smoke")
    parsed = extract_json_from_markdown(rendered)

    assert "# Elite Local Eval Suite" in rendered
    assert parsed["scope"] == "smoke"
    assert parsed["passed"] is True
    assert "task_success" in parsed["scorecard_dimensions"]
