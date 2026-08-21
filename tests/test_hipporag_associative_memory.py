"""
Unit tests for HippoRAG 2 Personalized PageRank Associative Memory Engine (core/memory/hipporag.py).
"""

from __future__ import annotations

import time
from core.memory.hipporag import (
    HippoRAGAssociativeEngine,
    AssociativeRecallResult,
)


def test_hipporag_empty_graph():
    engine = HippoRAGAssociativeEngine()
    res = engine.associative_recall("empty query")
    assert isinstance(res, AssociativeRecallResult)
    assert res.seed_nodes_count == 0
    assert len(res.ranked_memories) == 0


def test_hipporag_personalized_pagerank_and_multi_hop():
    engine = HippoRAGAssociativeEngine()

    # Create multi-hop graph:
    # (auth_v1) --[DEPRECATED_BY]--> (oauth2_migration) --[INVARIANT_ON]--> (rate_limiter) --[PROTECTS]--> (checkout_api)
    engine.add_node("node_auth_v1", "legacy_auth", {"description": "Legacy MD5 user authentication endpoint"})
    engine.add_node("node_oauth2", "oauth2_migration", {"description": "RFC 6749 OAuth2 JWT migration layer"})
    engine.add_node("node_limiter", "rate_limiter", {"description": "Token bucket rate limiter on requests"})
    engine.add_node("node_checkout", "checkout_api", {"description": "Stripe payment checkout processing endpoint"})

    engine.add_edge("node_auth_v1", "node_oauth2", "DEPRECATED_BY")
    engine.add_edge("node_oauth2", "node_limiter", "INVARIANT_ON")
    engine.add_edge("node_limiter", "node_checkout", "PROTECTS")

    # Query for "MD5" -> Seeds at node_auth_v1, should propagate multi-hop to node_oauth2 and node_limiter
    res = engine.associative_recall("MD5 authentication", top_k=4)
    assert res.seed_nodes_count >= 1
    assert len(res.ranked_memories) >= 3

    top_node = res.ranked_memories[0]
    assert top_node.id == "node_auth_v1"
    assert top_node.ppr_score > 0.0

    # Verify associative propagation (node_oauth2 should have higher score than distant node_checkout)
    scores = {m.id: m.final_score for m in res.ranked_memories}
    assert scores["node_oauth2"] > scores["node_checkout"]


def test_hipporag_ebbinghaus_temporal_decay():
    engine = HippoRAGAssociativeEngine()
    now = time.time()

    # Fresh node (created now)
    engine.add_node("fresh_node", "fact", {"text": "database migration rule"}, timestamp=now)
    # Stale node (created 30 days ago)
    engine.add_node("stale_node", "fact", {"text": "database migration rule"}, timestamp=now - (30 * 86400))

    res = engine.associative_recall("database migration", top_k=2)
    assert len(res.ranked_memories) == 2
    fresh = next(m for m in res.ranked_memories if m.id == "fresh_node")
    stale = next(m for m in res.ranked_memories if m.id == "stale_node")

    # Fresh node should have higher temporal weight than stale node
    assert fresh.temporal_weight > stale.temporal_weight
    assert fresh.final_score > stale.final_score
