"""Regression checks for the telemetry UI's SQLite contract."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.memory.persistent_store import EliteStore

_DASHBOARD_DB_ACTION = (
    Path(__file__).resolve().parents[1] / "telemetry-ui" / "src" / "app" / "actions" / "db.ts"
)


def test_dashboard_reads_the_consolidated_graph_schema(tmp_path):
    store = EliteStore(str(tmp_path / "brain"))
    store.graph.add_node("Decision", {"title": "Use one database"}, node_id="decision-1")
    store.graph.add_node("Hypothesis", {"state": "PENDING"}, node_id="hypothesis-1")
    store.graph.add_edge("decision-1", "hypothesis-1", "supports")

    with sqlite3.connect(store.db_path) as connection:
        nodes = connection.execute(
            "SELECT id, label, properties FROM graph_nodes ORDER BY created_at ASC"
        ).fetchall()
        edges = connection.execute(
            "SELECT id, source_id, target_id, relation FROM graph_edges ORDER BY valid_from ASC"
        ).fetchall()

    assert [node[:2] for node in nodes] == [
        ("decision-1", "Decision"),
        ("hypothesis-1", "Hypothesis"),
    ]
    assert [(edge[1], edge[2], edge[3]) for edge in edges] == [
        ("decision-1", "hypothesis-1", "supports")
    ]

    source = _DASHBOARD_DB_ACTION.read_text(encoding="utf-8")
    assert "path.join(BRAIN_DIR, 'elite.db')" in source
    assert "elite_graph.db" not in source
    assert "FROM graph_nodes" in source
    assert "FROM graph_edges" in source
    assert "datetime(valid_from)" in source
    assert "datetime(valid_to)" in source
