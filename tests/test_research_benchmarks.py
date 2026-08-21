from core.eval.research_benchmarks import (
    BENCHMARK_CATALOG,
    ELITE_SCORECARD,
    benchmark_catalog_markdown,
    budget_policy_markdown,
    recommend_budget_tier,
    scorecard_markdown,
)


def test_benchmark_catalog_includes_agentic_and_tool_use_sources():
    names = {source.name for source in BENCHMARK_CATALOG}

    assert "SWE-bench Verified" in names
    assert "API-Bank" in names
    assert "ToolBench" in names
    assert "AgentBench" in names
    assert "HELM-style multi-metric evaluation" in names
    assert "Brier score calibration" in names


def test_scorecard_weights_sum_to_one():
    total = sum(dimension.weight for dimension in ELITE_SCORECARD)

    assert round(total, 6) == 1.0


def test_benchmark_catalog_markdown_can_filter_task_class():
    rendered = benchmark_catalog_markdown("tool_use")

    assert "API-Bank" in rendered
    assert "ToolBench" in rendered
    assert "SWE-bench Verified" not in rendered


def test_scorecard_markdown_mentions_outcome_not_just_process():
    rendered = scorecard_markdown()

    assert "task_success" in rendered
    assert "tool_efficiency" in rendered
    assert "evidence_quality" in rendered
    assert "Total weight:** 1.00" in rendered


def test_roi_budget_recommends_research_grade_for_benchmarks():
    policy = recommend_budget_tier("compare research papers and benchmarks for coding agents")

    assert policy.tier == "research_grade"
    assert "elite_verify:evidence" in policy.required_checks


def test_roi_budget_recommends_high_risk_for_security_production():
    policy = recommend_budget_tier("fix production authentication migration", complexity=4)

    assert policy.tier == "high_risk"
    assert "elite_verify:constraints" in policy.required_checks


def test_budget_policy_markdown_is_actionable():
    rendered = budget_policy_markdown("quick typo", complexity=1)

    assert "Adaptive ROI / Tool Budget Policy" in rendered
    assert "Recommended tier" in rendered
    assert "Policy Table" in rendered
