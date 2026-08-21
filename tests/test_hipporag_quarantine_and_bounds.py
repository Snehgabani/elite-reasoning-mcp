from core.memory.hipporag import HippoRAGAssociativeEngine


def test_quarantine_damping_in_associative_recall():
    engine = HippoRAGAssociativeEngine()
    # Clean approved node
    engine.add_node(
        "mem_1",
        label="decision",
        properties={"text": "database auth postgres", "trust_score": 0.9, "quarantined": False},
    )
    # Quarantined / low-trust node
    engine.add_node(
        "mem_2", label="decision", properties={"text": "database auth mongodb", "trust_score": 0.3, "quarantined": True}
    )

    result = engine.associative_recall(query="database auth", top_k=2)
    assert len(result.ranked_memories) == 2
    # Approved memory must rank first due to 0.2x damping on quarantined node
    assert result.ranked_memories[0].id == "mem_1"
    assert result.ranked_memories[1].id == "mem_2"
    assert result.ranked_memories[0].final_score > result.ranked_memories[1].final_score


def test_remove_node_provenance_pruning():
    engine = HippoRAGAssociativeEngine()
    engine.add_node("node_a", label="concept", properties={"text": "microservice"})
    engine.add_node("node_b", label="concept", properties={"text": "gateway"})
    engine.add_edge("node_a", "node_b", relation="connects_to")

    assert len(engine._in_memory_nodes) == 2
    assert len(engine._in_memory_edges) == 1

    engine.remove_node("node_a")
    assert len(engine._in_memory_nodes) == 1
    assert "node_a" not in engine._in_memory_nodes
    assert len(engine._in_memory_edges) == 0


def test_bounded_graph_expansion():
    engine = HippoRAGAssociativeEngine()
    # Add 600 nodes
    for i in range(600):
        engine.add_node(f"node_{i}", label="fact", properties={"text": f"token item {i}"})
        if i > 0:
            engine.add_edge(f"node_{i - 1}", f"node_{i}", relation="next")

    result = engine.associative_recall(query="item 10", top_k=5, max_nodes_bound=50)
    assert len(result.ranked_memories) <= 5
    assert result.latency_ms < 50.0  # Must be fast and bounded
