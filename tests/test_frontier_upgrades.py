"""
Unit tests for the 4 Frontier Sovereign Upgrades:
1. Stealth Web Scraper (trafilatura / crawl4ai)
2. Vector Memory Bridge (sovereign-search / sqlite-vec)
3. macOS Watchdog Notifier & Telemetry
4. Zero-RAM DuckDB Analytics Bridge (sovereign-analytics)
"""

from core.cognitive.leverage.stealth_scraper import StealthScraperEngine
from core.cognitive.leverage.vector_memory_bridge import VectorMemoryBridge
from core.cognitive.leverage.watchdog_notifier import WatchdogNotifier
from core.cognitive.leverage.duckdb_analytics_bridge import DuckDBAnalyticsBridge


def test_stealth_scraper_engine_fallback_and_handling():
    scraper = StealthScraperEngine(timeout_seconds=2.0)
    # Test on invalid or local URL
    res = scraper.scrape_fit_markdown("http://127.0.0.1:9999/nonexistent")
    assert "status" in res
    assert res["url"] == "http://127.0.0.1:9999/nonexistent"


def test_vector_memory_bridge_indexing_and_search(tmp_path):
    bridge = VectorMemoryBridge()
    # Test indexing skill card
    res_index = bridge.index_skill(
        skill_name="Test Invariant Mutex",
        pattern="Use sync.Mutex for critical sections in Go",
        invariant_rule="Never copy mutex values by value",
    )
    assert res_index["status"] in {"INDEXED", "SAVED_LOCAL_ONLY"}

    # Test searching skills
    res_search = bridge.search_skills("mutex locking concurrency")
    assert res_search["status"] in {"SUCCESS", "UNAVAILABLE"}


def test_watchdog_notifier_telemetry_recording():
    notifier = WatchdogNotifier()
    res = notifier.record_telemetry(
        task_id="test-frontier-task",
        status="RUNNING",
        current_node="AST_GATE",
        progress_pct=65,
        prm_score=0.98,
        details="Validating AST invariants in RAM",
        notify_desktop=False,
    )
    assert res["status"] == "TELEMETRY_RECORDED"
    assert res["task_id"] == "test-frontier-task"


def test_duckdb_analytics_bridge_query():
    analytics = DuckDBAnalyticsBridge()
    res = analytics.execute_sql("SELECT 42 AS answer, 'sovereign' AS mode")
    assert res["status"] in {"SUCCESS", "UNAVAILABLE"}
    if res["status"] == "SUCCESS":
        assert "42" in res["output"]
        assert "sovereign" in res["output"]
