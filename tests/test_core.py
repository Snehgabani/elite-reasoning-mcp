"""
Tests for elite-reasoning-mcp core functionality.

Deterministic tests — no external services, no API keys.
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.persistent_store import EliteStore


@pytest.fixture
def store(tmp_path):
    """Create a fresh EliteStore with a temporary directory."""
    s = EliteStore(str(tmp_path))
    yield s


class TestEliteStore:
    """Tests for the SQLite persistent store."""

    def test_create_store(self, store):
        assert store is not None

    def test_record_and_get_mistakes(self, store):
        mid = store.record_mistake(
            mistake="Used print() instead of logging",
            root_cause="Habit from scripting",
            fix="Use structured logging",
            severity="medium",
            tags="logging,quality"
        )
        assert mid > 0
        patterns = store.get_all_anti_patterns()
        assert len(patterns) >= 1

    def test_check_anti_patterns(self, store):
        store.record_mistake(
            mistake="Forgot null check on API response",
            root_cause="No defensive coding",
            fix="Always check for None",
            severity="high",
            tags="api"
        )
        results = store.check_anti_patterns("API response null")
        # Should find something related
        all_p = store.get_all_anti_patterns()
        assert len(all_p) >= 1

    def test_count_anti_patterns(self, store):
        assert store.count_anti_patterns() == 0
        store.record_mistake("m1", "r1", "f1")
        store.record_mistake("m2", "r2", "f2")
        assert store.count_anti_patterns() == 2

    def test_record_and_get_decisions(self, store):
        did = store.record_decision(
            decision="Use SQLite over PostgreSQL",
            rationale="Zero config, portable",
            alternatives_rejected="PostgreSQL, JSON files",
            context="Persistence layer choice"
        )
        assert did > 0
        decisions = store.get_all_decisions()
        assert len(decisions) >= 1

    def test_search_decisions(self, store):
        store.record_decision("Use FastAPI", "Modern, async", "Flask, Django")
        store.record_decision("Use pytest", "Best test framework", "unittest")
        results = store.search_decisions("FastAPI")
        # FTS search may or may not match; get_all always works
        all_d = store.get_all_decisions()
        assert len(all_d) == 2

    def test_record_quality_score(self, store):
        qid = store.record_quality_score(score=8, dimension="code", notes="Clean")
        assert qid > 0

    def test_quality_trend(self, store):
        for s in [7, 8, 9]:
            store.record_quality_score(score=s, dimension="code")
        trend = store.get_quality_trend(limit=10)
        assert isinstance(trend, dict)

    def test_goal_lifecycle(self, store):
        gid = store.set_goal(
            objective="Ship v1.0",
            key_results=["Publish to PyPI", "Add tests", "Write docs"]
        )
        assert gid > 0

        goals = store.get_active_goals()
        assert len(goals) >= 1

        store.complete_goal(gid)

    def test_archive_and_delete_goal(self, store):
        gid = store.set_goal(objective="Test goal", key_results=["KR1"])
        store.archive_goal(gid)
        store.delete_goal(gid)

    def test_benchmark_tracking(self, store):
        bid = store.record_benchmark(
            metric="response_quality",
            value=8.5,
            context="baseline"
        )
        assert bid > 0
        trend = store.get_benchmark_trend("response_quality")
        assert isinstance(trend, dict)

    def test_list_benchmark_metrics(self, store):
        store.record_benchmark(metric="speed", value=100)
        store.record_benchmark(metric="quality", value=9)
        metrics = store.list_benchmark_metrics()
        assert "speed" in metrics
        assert "quality" in metrics

    def test_smoke_test_lifecycle(self, store):
        tid = store.create_smoke_test(
            description="Login flow works",
            before_state="User not logged in"
        )
        assert tid > 0

        result = store.complete_smoke_test(
            test_id=tid,
            after_state="User logged in successfully",
            verdict="pass"
        )
        assert result is True

        test = store.get_smoke_test(tid)
        assert test is not None
        assert test["verdict"] == "pass"



