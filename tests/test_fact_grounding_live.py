from core.evidence.query_planner import QueryPlanner
from core.evidence.fact_grounder import FActScoreGrounder
from core.evidence.grounded_search import EvidenceQuote, GroundedEvidence


def test_query_planner_decomposition():
    planner = QueryPlanner(current_year=2026)

    # Comparative inquiry
    plan = planner.plan("Compare DuckDB versus SQLite on Apple Silicon M2 performance")
    assert len(plan.sub_queries) >= 2
    assert any("DuckDB" in q.query_text for q in plan.sub_queries)

    # Temporal inquiry
    temporal_plan = planner.plan("What are the latest 2026 AI agent benchmarks?")
    assert temporal_plan.detected_temporal_year == 2026
    assert any(q.is_temporal for q in temporal_plan.sub_queries)


def test_fact_grounder_atomic_extraction():
    grounder = FActScoreGrounder()
    text = """
# Overview
DuckDB executes analytical queries in columnar format.
It uses vectorized CPU instructions on Apple Silicon M2.
SQLite stores records in row-oriented format.
"""
    claims = grounder.extract_atomic_propositions(text)
    assert len(claims) == 3
    assert any("columnar format" in c for c in claims)
    assert any("vectorized CPU" in c for c in claims)


def test_fact_grounder_evaluation_and_hallucination_detection():
    grounder = FActScoreGrounder(min_fact_score_threshold=0.70)

    evidence = GroundedEvidence(
        query="DuckDB architecture",
        quotes=(
            EvidenceQuote(
                url="https://duckdb.org/docs/overview",
                title="DuckDB Overview",
                quote="DuckDB executes analytical queries in columnar vectorized format.",
            ),
            EvidenceQuote(
                url="https://duckdb.org/docs/storage",
                title="Storage Format",
                quote="DuckDB persistent storage format supports zero copy streaming.",
            ),
        ),
        sources_fetched=2,
        sources_readable=2,
        degraded=False,
        uncertain=(),
        retrieved_at="2026-08-21T00:00:00Z",
    )

    # Valid supported draft
    supported_draft = """
According to https://duckdb.org/docs/overview, DuckDB executes analytical queries in columnar vectorized format.
Furthermore, persistent storage format supports zero copy streaming https://duckdb.org/docs/storage.
"""
    report = grounder.evaluate_grounding(supported_draft, evidence)
    assert report.passed is True
    assert report.fact_score >= 0.70
    assert len(report.hallucinated_urls) == 0

    # Draft with hallucinated URL
    hallucinated_draft = """
DuckDB is columnar https://fake-hallucinated-site.org/madeup.
"""
    bad_report = grounder.evaluate_grounding(hallucinated_draft, evidence)
    assert bad_report.passed is False
    assert "https://fake-hallucinated-site.org/madeup" in bad_report.hallucinated_urls
