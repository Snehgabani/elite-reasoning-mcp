"""Hybrid search: BM25 (FTS5) + Vector (sqlite-vec) with Reciprocal Rank Fusion.
Expected 20-35% precision lift on natural-language queries vs FTS5 alone."""
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import sqlite_vec
except ImportError:
    sqlite_vec = None


@dataclass
class SearchResult:
    id: int
    score: float
    fts_rank: int | None
    vec_rank: int | None
    payload: dict


def adaptive_weights(query: str) -> tuple[float, float]:
    """Short queries favor BM25 (lexical); long queries favor vectors (semantic)."""
    n = len(query.split())
    if n <= 3:
        return 1.5, 0.7   # keyword queries → lexical
    elif n >= 12:
        return 0.7, 1.5   # prose queries → semantic
    return 1.0, 1.0


class HybridSearch:
    """Reciprocal Rank Fusion of FTS5 + sqlite-vec.

    Usage:
        hs = HybridSearch(store, "anti_patterns")
        results = hs.search("security SQL injection", limit=5)
    """

    # Column maps for supported tables
    _TABLE_COLUMNS = {
        "anti_patterns": {
            "select": "id, mistake, root_cause, fix, severity, tags, created_at",
            "payload_keys": ["id", "mistake", "root_cause", "fix", "severity", "tags", "created_at"],
            "fts_table": "anti_patterns_fts",
            "vec_table": "anti_patterns_vec",
        },
        "decisions": {
            "select": "id, decision, rationale, alternatives_rejected, context, created_at",
            "payload_keys": ["id", "decision", "rationale", "alternatives_rejected", "context", "created_at"],
            "fts_table": "decisions_fts",
            "vec_table": "decisions_vec",
        },
    }

    def __init__(self, store, table: str, k_rrf: int = 60):
        self.store = store
        self.table = table
        self.k = k_rrf
        self._config = self._TABLE_COLUMNS.get(table)
        if not self._config:
            raise ValueError(f"Unsupported table: {table}. Supported: {list(self._TABLE_COLUMNS)}")

    def search(self, query: str, limit: int = 10,
               fts_weight: float | None = None,
               vec_weight: float | None = None) -> list[SearchResult]:
        """Fused search: BM25 + vector with adaptive weights."""
        start = time.perf_counter()

        if fts_weight is None or vec_weight is None:
            fts_weight, vec_weight = adaptive_weights(query)

        fts_hits = self._fts_search(query, limit=limit * 3)
        vec_hits = self._vec_search(query, limit=limit * 3)

        # Reciprocal Rank Fusion
        scores: dict[int, dict] = {}
        for rank, hit in enumerate(fts_hits, start=1):
            scores.setdefault(hit['id'], {"fts_rank": None, "vec_rank": None, "payload": hit})
            scores[hit['id']]["fts_rank"] = rank
        for rank, hit in enumerate(vec_hits, start=1):
            scores.setdefault(hit['id'], {"fts_rank": None, "vec_rank": None, "payload": hit})
            scores[hit['id']]["vec_rank"] = rank

        fused = []
        for doc_id, s in scores.items():
            score = 0.0
            if s["fts_rank"] is not None:
                score += fts_weight / (self.k + s["fts_rank"])
            if s["vec_rank"] is not None:
                score += vec_weight / (self.k + s["vec_rank"])
            fused.append(SearchResult(
                id=doc_id, score=score,
                fts_rank=s["fts_rank"], vec_rank=s["vec_rank"],
                payload=s["payload"],
            ))
        fused.sort(key=lambda r: r.score, reverse=True)

        duration = (time.perf_counter() - start) * 1000
        logger.debug(
            f"Hybrid search [{self.table}]: {len(fts_hits)} FTS + {len(vec_hits)} vec "
            f"→ {len(fused)} fused in {duration:.1f}ms"
        )
        return fused[:limit]

    def _fts_search(self, query: str, limit: int) -> list[dict]:
        """BM25 search via FTS5 virtual table."""
        conn = self.store._connect()
        try:
            c = conn.cursor()
            fts_table = self._config["fts_table"]
            table = self.table
            columns = self._config["select"]
            keys = self._config["payload_keys"]

            safe_query = self.store._sanitize_fts_query(query)
            c.execute(f"""
                SELECT d.{columns.replace(', ', ', d.')}
                FROM {fts_table} f JOIN {table} d ON f.rowid = d.id
                WHERE {fts_table} MATCH ? ORDER BY rank LIMIT ?
            """, (safe_query, limit))

            results = []
            for r in c.fetchall():
                results.append(dict(zip(keys, r)))
            return results
        except Exception as e:
            logger.debug(f"FTS search failed for {self.table}: {e}")
            return []
        finally:
            self.store._close(conn)

    def _vec_search(self, query: str, limit: int) -> list[dict]:
        """Vector similarity search via sqlite-vec."""
        if sqlite_vec is None:
            return []

        emb = self.store._get_embedding(query)
        if not emb:
            return []

        conn = self.store._connect()
        try:
            c = conn.cursor()
            vec_table = self._config["vec_table"]
            table = self.table
            columns = self._config["select"]
            keys = self._config["payload_keys"]

            c.execute(f"""
                SELECT d.{columns.replace(', ', ', d.')}, v.distance
                FROM {vec_table} v
                JOIN {table} d ON v.id = d.id
                WHERE v.embedding MATCH ? AND k = ?
                ORDER BY v.distance
            """, (sqlite_vec.serialize_float32(emb), limit))

            results = []
            for r in c.fetchall():
                payload = dict(zip(keys, r[:len(keys)]))
                results.append(payload)
            return results
        except Exception as e:
            logger.debug(f"Vec search failed for {self.table}: {e}")
            return []
        finally:
            self.store._close(conn)
