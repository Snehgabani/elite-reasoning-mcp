"""
Tests for core.memory.graph_store.TemporalGraphStore.

Covers:
  - Initialization (DB file + tables)
  - add_node + query_nodes (get_node, query_graph)
  - add_edge + get_edges (via query_graph)
  - query_subgraph (label filtering, temporal edge validity)
  - Connection caching (thread-local)
"""

import json
import os
import sqlite3
import tempfile
import threading
from datetime import datetime, timedelta, timezone

import pytest

from core.memory.graph_store import TemporalGraphStore


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture()
def db_path():
    d = tempfile.mkdtemp(prefix="graph_test_")
    yield os.path.join(d, "test_graph.db")


@pytest.fixture()
def graph(db_path):
    return TemporalGraphStore(db_path)


# ──────────────────────────────────────────────
# 1. Initialization
# ──────────────────────────────────────────────

class TestInitialization:
    def test_creates_db_file(self, db_path):
        TemporalGraphStore(db_path)
        assert os.path.isfile(db_path)

    def test_expected_tables_exist(self, db_path):
        TemporalGraphStore(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "graph_nodes" in tables
        assert "graph_edges" in tables

    def test_indexes_created(self, db_path):
        TemporalGraphStore(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "idx_edge_source" in indexes
        assert "idx_edge_target" in indexes
        assert "idx_node_label" in indexes

    def test_db_path_attribute(self, graph, db_path):
        assert graph.db_path == db_path


# ──────────────────────────────────────────────
# 2. add_node + query_nodes
# ──────────────────────────────────────────────

class TestNodes:
    def test_add_node_returns_id(self, graph):
        nid = graph.add_node("TestLabel", {"key": "value"})
        assert isinstance(nid, str)
        assert len(nid) > 0

    def test_add_node_with_custom_id(self, graph):
        nid = graph.add_node("Foo", node_id="custom_123")
        assert nid == "custom_123"

    def test_add_node_generates_uuid(self, graph):
        nid = graph.add_node("Bar")
        # UUID format: 8-4-4-4-12 hex chars
        parts = nid.split("-")
        assert len(parts) == 5

    def test_get_node(self, graph):
        nid = graph.add_node("Person", {"name": "Alice", "age": 30})
        node = graph.get_node(nid)
        assert node is not None
        assert node["id"] == nid
        assert node["label"] == "Person"
        assert node["properties"]["name"] == "Alice"
        assert node["properties"]["age"] == 30
        assert "created_at" in node

    def test_get_node_nonexistent(self, graph):
        assert graph.get_node("does_not_exist") is None

    def test_add_node_upserts_on_same_id(self, graph):
        graph.add_node("V1", {"x": 1}, node_id="n1")
        graph.add_node("V2", {"x": 2}, node_id="n1")
        node = graph.get_node("n1")
        assert node["label"] == "V2"
        assert node["properties"]["x"] == 2

    def test_add_node_no_properties(self, graph):
        nid = graph.add_node("Empty")
        node = graph.get_node(nid)
        assert node["properties"] == {}

    def test_query_graph_returns_all_nodes(self, graph):
        graph.add_node("A", node_id="a1")
        graph.add_node("B", node_id="b1")
        result = graph.query_graph()
        assert len(result) == 2
        ids = {n["id"] for n in result}
        assert ids == {"a1", "b1"}

    def test_query_graph_filter_by_label(self, graph):
        graph.add_node("Cat", node_id="c1")
        graph.add_node("Dog", node_id="d1")
        graph.add_node("Cat", node_id="c2")
        result = graph.query_graph(node_label="Cat")
        assert len(result) == 2
        assert all(n["label"] == "Cat" for n in result)

    def test_query_graph_label_no_match(self, graph):
        graph.add_node("Cat", node_id="c1")
        result = graph.query_graph(node_label="Unicorn")
        assert result == []


# ──────────────────────────────────────────────
# 3. add_edge + get_edges
# ──────────────────────────────────────────────

class TestEdges:
    def test_add_edge_returns_id(self, graph):
        graph.add_node("A", node_id="a")
        graph.add_node("B", node_id="b")
        eid = graph.add_edge("a", "b", "KNOWS")
        assert isinstance(eid, str)
        assert len(eid) > 0

    def test_edge_appears_in_query_graph(self, graph):
        graph.add_node("A", node_id="a")
        graph.add_node("B", node_id="b")
        graph.add_edge("a", "b", "LIKES", properties={"weight": 0.9})
        result = graph.query_graph()
        node_a = [n for n in result if n["id"] == "a"][0]
        assert len(node_a["edges"]) == 1
        assert node_a["edges"][0]["target_id"] == "b"
        assert node_a["edges"][0]["relation"] == "LIKES"
        assert node_a["edges"][0]["properties"]["weight"] == 0.9

    def test_edge_not_on_target_node(self, graph):
        """Edges are outgoing: source node has the edge, target does not."""
        graph.add_node("A", node_id="a")
        graph.add_node("B", node_id="b")
        graph.add_edge("a", "b", "FOLLOWS")
        result = graph.query_graph()
        node_b = [n for n in result if n["id"] == "b"][0]
        assert len(node_b["edges"]) == 0

    def test_multiple_edges(self, graph):
        graph.add_node("X", node_id="x")
        graph.add_node("Y", node_id="y")
        graph.add_node("Z", node_id="z")
        graph.add_edge("x", "y", "R1")
        graph.add_edge("x", "z", "R2")
        result = graph.query_graph()
        node_x = [n for n in result if n["id"] == "x"][0]
        assert len(node_x["edges"]) == 2

    def test_edge_default_properties(self, graph):
        graph.add_node("A", node_id="a")
        graph.add_node("B", node_id="b")
        graph.add_edge("a", "b", "REL")
        result = graph.query_graph()
        node_a = [n for n in result if n["id"] == "a"][0]
        assert node_a["edges"][0]["properties"] == {}


# ──────────────────────────────────────────────
# 4. query_subgraph — temporal edge validity
# ──────────────────────────────────────────────

class TestTemporalEdges:
    def test_edge_valid_at_query_time(self, graph):
        graph.add_node("A", node_id="a")
        graph.add_node("B", node_id="b")
        now = datetime.now(timezone.utc)
        past = (now - timedelta(days=1)).isoformat()
        future = (now + timedelta(days=1)).isoformat()
        graph.add_edge("a", "b", "ACTIVE", valid_from=past, valid_to=future)
        result = graph.query_graph(at_time=now.isoformat())
        node_a = [n for n in result if n["id"] == "a"][0]
        assert len(node_a["edges"]) == 1

    def test_edge_expired_at_query_time(self, graph):
        graph.add_node("A", node_id="a")
        graph.add_node("B", node_id="b")
        now = datetime.now(timezone.utc)
        old_from = (now - timedelta(days=10)).isoformat()
        old_to = (now - timedelta(days=5)).isoformat()
        graph.add_edge("a", "b", "EXPIRED", valid_from=old_from, valid_to=old_to)
        result = graph.query_graph(at_time=now.isoformat())
        node_a = [n for n in result if n["id"] == "a"][0]
        assert len(node_a["edges"]) == 0

    def test_edge_not_yet_valid(self, graph):
        graph.add_node("A", node_id="a")
        graph.add_node("B", node_id="b")
        now = datetime.now(timezone.utc)
        future_from = (now + timedelta(days=5)).isoformat()
        future_to = (now + timedelta(days=10)).isoformat()
        graph.add_edge("a", "b", "FUTURE", valid_from=future_from, valid_to=future_to)
        result = graph.query_graph(at_time=now.isoformat())
        node_a = [n for n in result if n["id"] == "a"][0]
        assert len(node_a["edges"]) == 0

    def test_edge_with_null_valid_to(self, graph):
        """An edge with no valid_to (open-ended) should always be valid."""
        graph.add_node("A", node_id="a")
        graph.add_node("B", node_id="b")
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        graph.add_edge("a", "b", "OPEN", valid_from=past, valid_to=None)
        result = graph.query_graph()
        node_a = [n for n in result if n["id"] == "a"][0]
        assert len(node_a["edges"]) == 1

    def test_mixed_temporal_edges(self, graph):
        """Among several edges, only valid ones appear."""
        graph.add_node("A", node_id="a")
        graph.add_node("B", node_id="b")
        graph.add_node("C", node_id="c")
        now = datetime.now(timezone.utc)
        # Active edge
        graph.add_edge(
            "a", "b", "ACTIVE",
            valid_from=(now - timedelta(days=1)).isoformat(),
            valid_to=(now + timedelta(days=1)).isoformat(),
        )
        # Expired edge
        graph.add_edge(
            "a", "c", "EXPIRED",
            valid_from=(now - timedelta(days=10)).isoformat(),
            valid_to=(now - timedelta(days=5)).isoformat(),
        )
        result = graph.query_graph(at_time=now.isoformat())
        node_a = [n for n in result if n["id"] == "a"][0]
        assert len(node_a["edges"]) == 1
        assert node_a["edges"][0]["relation"] == "ACTIVE"


# ──────────────────────────────────────────────
# 5. Hypothesis & Prospective Failure helpers
# ──────────────────────────────────────────────

class TestHypothesisAndPrediction:
    def test_add_hypothesis(self, graph):
        nid = graph.add_hypothesis("caching helps", "latency drops 50%")
        node = graph.get_node(nid)
        assert node["label"] == "Hypothesis"
        assert node["properties"]["state"] == "PENDING"

    def test_resolve_hypothesis(self, graph):
        nid = graph.add_hypothesis("X works", "Y happens")
        graph.resolve_hypothesis(nid, "CONFIRMED", "saw Y")
        node = graph.get_node(nid)
        assert node["properties"]["state"] == "CONFIRMED"
        assert node["properties"]["evidence"] == "saw Y"

    def test_resolve_hypothesis_invalid_node(self, graph):
        with pytest.raises(ValueError, match="not found"):
            graph.resolve_hypothesis("bad_id", "X", "Y")

    def test_resolve_hypothesis_wrong_label(self, graph):
        nid = graph.add_node("Decision", {"x": 1})
        with pytest.raises(ValueError, match="not a Hypothesis"):
            graph.resolve_hypothesis(nid, "X", "Y")

    def test_add_prospective_failure(self, graph):
        nid = graph.add_prospective_failure("deploy", "OOM", "load > 10k")
        node = graph.get_node(nid)
        assert node["label"] == "Prospective_Failure"
        assert node["properties"]["state"] == "UNRESOLVED"

    def test_get_unresolved_predictions(self, graph):
        graph.add_prospective_failure("a1", "f1", "t1")
        nid2 = graph.add_prospective_failure("a2", "f2", "t2")
        graph.resolve_prediction(nid2, True)
        unresolved = graph.get_unresolved_predictions()
        assert len(unresolved) == 1
        assert unresolved[0]["properties"]["state"] == "UNRESOLVED"

    def test_resolve_prediction_true(self, graph):
        nid = graph.add_prospective_failure("a", "f", "t")
        graph.resolve_prediction(nid, True)
        node = graph.get_node(nid)
        assert node["properties"]["state"] == "TRUE"

    def test_resolve_prediction_false(self, graph):
        nid = graph.add_prospective_failure("a", "f", "t")
        graph.resolve_prediction(nid, False)
        node = graph.get_node(nid)
        assert node["properties"]["state"] == "FALSE"

    def test_resolve_prediction_invalid(self, graph):
        with pytest.raises(ValueError):
            graph.resolve_prediction("nope", True)


# ──────────────────────────────────────────────
# 6. Connection caching
# ──────────────────────────────────────────────

class TestConnectionCaching:
    def test_same_thread_reuses_connection(self, graph):
        c1 = graph._get_conn()
        c2 = graph._get_conn()
        assert c1 is c2

    def test_different_threads_get_different_connections(self, graph):
        conns = {}
        barrier = threading.Barrier(2)

        def worker(name):
            c = graph._get_conn()
            barrier.wait()
            conns[name] = c

        t1 = threading.Thread(target=worker, args=("a",))
        t2 = threading.Thread(target=worker, args=("b",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert conns["a"] is not conns["b"]

    def test_recovers_from_stale_connection(self, graph):
        c1 = graph._get_conn()
        c1.close()
        # Next call should detect the stale conn and create a fresh one
        c2 = graph._get_conn()
        assert c2 is not c1
        c2.execute("SELECT 1")  # should work
