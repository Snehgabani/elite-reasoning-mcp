import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class TemporalGraphStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self):
        cached = getattr(self._local, 'conn', None)
        if cached is not None:
            try:
                cached.execute("SELECT 1")
                return cached
            except Exception:
                self._local.conn = None
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        self._local.conn = conn
        return conn

    def _close(self, conn):
        if getattr(self._local, 'in_transaction', False):
            return
        conn.commit()
        conn.close()
        self._local.conn = None

    def _init_db(self):
        conn = self._get_conn()
        try:
            # Nodes table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS graph_nodes (
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    properties TEXT,
                    created_at TEXT NOT NULL
                )
            ''')
            # Edges table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS graph_edges (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    valid_from TEXT,
                    valid_to TEXT,
                    properties TEXT,
                    FOREIGN KEY (source_id) REFERENCES graph_nodes(id),
                    FOREIGN KEY (target_id) REFERENCES graph_nodes(id)
                )
            ''')
            # Indexes for faster traversal
            conn.execute('CREATE INDEX IF NOT EXISTS idx_edge_source ON graph_edges(source_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_edge_target ON graph_edges(target_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_node_label ON graph_nodes(label)')
        finally:
            self._close(conn)

    def add_node(self, label: str, properties: Dict[str, Any] = None, node_id: str = None) -> str:
        """Add a new node to the graph."""
        nid = node_id or str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        props_str = json.dumps(properties) if properties else "{}"

        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO graph_nodes (id, label, properties, created_at) VALUES (?, ?, ?, ?)",
                (nid, label, props_str, created_at)
            )
        finally:
            self._close(conn)
        return nid

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            cur = conn.execute("SELECT * FROM graph_nodes WHERE id = ?", (node_id,))
            row = cur.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "label": row["label"],
                    "properties": json.loads(row["properties"]),
                    "created_at": row["created_at"]
                }
            return None
        finally:
            if not getattr(self._local, 'in_transaction', False):
                conn.close()

    def add_edge(self, source_id: str, target_id: str, relation: str, properties: Dict[str, Any] = None, valid_from: str = None, valid_to: str = None) -> str:
        """Add a temporal edge between two nodes."""
        eid = str(uuid.uuid4())
        props_str = json.dumps(properties) if properties else "{}"
        v_from = valid_from or datetime.now(timezone.utc).isoformat()

        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO graph_edges (id, source_id, target_id, relation, valid_from, valid_to, properties) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (eid, source_id, target_id, relation, v_from, valid_to, props_str)
            )
        finally:
            self._close(conn)
        return eid

    def add_hypothesis(self, hypothesis: str, prediction: str) -> str:
        """
        Create a new Hypothesis node in PENDING state.
        """
        properties = {
            "hypothesis": hypothesis,
            "prediction": prediction,
            "state": "PENDING"
        }
        return self.add_node("Hypothesis", properties)

    def resolve_hypothesis(self, node_id: str, outcome: str, evidence: str) -> None:
        """
        Update a Hypothesis or Prospective_Failure node with its resolution outcome.
        """
        node = self.get_node(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found.")

        if node["label"] not in ("Hypothesis", "Prospective_Failure"):
            raise ValueError(f"Node {node_id} is a {node['label']}, not a Hypothesis or Prospective_Failure.")

        properties = node["properties"]
        properties["state"] = outcome
        properties["evidence"] = evidence
        properties["evaluated_at"] = datetime.now(timezone.utc).isoformat()

        props_str = json.dumps(properties)
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE graph_nodes SET properties = ? WHERE id = ?",
                (props_str, node_id)
            )
        finally:
            self._close(conn)

    def add_prospective_failure(self, action: str, predicted_failure: str, trigger_condition: str) -> str:
        """
        Record a simulated future failure mode into the graph.
        """
        properties = {
            "action": action,
            "predicted_failure": predicted_failure,
            "trigger_condition": trigger_condition,
            "state": "UNRESOLVED"
        }
        return self.add_node("Prospective_Failure", properties)

    def get_unresolved_predictions(self) -> List[Dict[str, Any]]:
        """
        Fetch all unresolved Prospective_Failure nodes.
        """
        nodes = []
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT * FROM graph_nodes WHERE label = 'Prospective_Failure'")
            for row in cursor.fetchall():
                props = json.loads(row['properties'])
                if props.get('state') == 'UNRESOLVED':
                    nodes.append({
                        "id": row['id'],
                        "label": row['label'],
                        "created_at": row['created_at'],
                        "properties": props
                    })
        finally:
            if not getattr(self._local, 'in_transaction', False):
                conn.close()
        return nodes

    def resolve_prediction(self, node_id: str, occurred: bool) -> None:
        """
        Mark a Prospective_Failure as TRUE (it happened) or FALSE (did not happen).
        """
        node = self.get_node(node_id)
        if not node or node["label"] != "Prospective_Failure":
            raise ValueError(f"Valid Prospective_Failure node {node_id} not found.")

        properties = node["properties"]
        properties["state"] = "TRUE" if occurred else "FALSE"
        properties["evaluated_at"] = datetime.now(timezone.utc).isoformat()

        props_str = json.dumps(properties)
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE graph_nodes SET properties = ? WHERE id = ?",
                (props_str, node_id)
            )
        finally:
            self._close(conn)

    def query_graph(self, at_time: str = None, node_label: str = None) -> List[Dict[str, Any]]:
        """
        Query the graph, optionally filtering for relationships valid at a specific time.
        Returns a list of nodes and their outgoing edges.
        """
        query_time = at_time or datetime.now(timezone.utc).isoformat()

        nodes_query = "SELECT * FROM graph_nodes"
        params = []
        if node_label:
            nodes_query += " WHERE label = ?"
            params.append(node_label)

        result = []
        conn = self._get_conn()
        try:
            nodes = conn.execute(nodes_query, params).fetchall()
            for node in nodes:
                node_data = {
                    "id": node["id"],
                    "label": node["label"],
                    "properties": json.loads(node["properties"]),
                    "edges": []
                }

                # Fetch valid edges
                edges = conn.execute('''
                    SELECT * FROM graph_edges 
                    WHERE source_id = ? 
                    AND (valid_from IS NULL OR valid_from <= ?)
                    AND (valid_to IS NULL OR valid_to > ?)
                ''', (node["id"], query_time, query_time)).fetchall()

                for edge in edges:
                    node_data["edges"].append({
                        "id": edge["id"],
                        "target_id": edge["target_id"],
                        "relation": edge["relation"],
                        "properties": json.loads(edge["properties"])
                    })

                result.append(node_data)
        finally:
            if not getattr(self._local, 'in_transaction', False):
                conn.close()

        return result
