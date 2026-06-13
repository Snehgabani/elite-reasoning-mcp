def register(mcp, store, orchestrator=None):
    @mcp.tool()
    def record_hypothesis(hypothesis: str, prediction: str) -> str:
        """
            Record a prospective hypothesis and expectation into the Temporal Knowledge Graph.
            Args:
                hypothesis: The core assumption or scientific hypothesis being tested.
                prediction: What outcome will validate or falsify this hypothesis.
            """
        try:
            node_id = store.graph.add_hypothesis(hypothesis, prediction)
            return f'✅ Hypothesis recorded with Node ID: {node_id}. State is PENDING.'
        except Exception as e:
            return f'❌ Failed to record hypothesis: {str(e)}'

    @mcp.tool()
    def resolve_hypothesis(node_id: str, outcome: str, evidence: str) -> str:
        """
            Resolve a previously recorded hypothesis as VALIDATED or FALSIFIED.
            Args:
                node_id: The exact ID of the Hypothesis node.
                outcome: Must be exactly 'VALIDATED' or 'FALSIFIED'.
                evidence: Why this outcome was reached.
            """
        if outcome not in ['VALIDATED', 'FALSIFIED']:
            return "❌ outcome must be 'VALIDATED' or 'FALSIFIED'"
        try:
            store.graph.resolve_hypothesis(node_id, outcome, evidence)
            return f'✅ Hypothesis {node_id} resolved as {outcome}.'
        except Exception as e:
            return f'❌ Failed to resolve hypothesis: {str(e)}'

    @mcp.tool()
    def ingest_context(context: str) -> str:
        """
            Ingest raw context into the temporal knowledge graph using LangGraph background orchestration.
            Args:
                context: The raw text, discussion, or logs to analyze.
            """
        try:
            from core.orchestration.langgraph_nodes import build_ingestion_graph
            workflow = build_ingestion_graph()
            result = workflow.invoke({'raw_text': context, 'extracted_entities': [], 'graph_edges_to_create': [], 'synthesis_message': ''})
            count = 0
            for edge in result.get('graph_edges_to_create', []):
                source_id = f"ctx_{hash(edge['source_label'])}"
                target_id = f"ent_{hash(edge['target_label'])}"
                store.graph.add_node(edge['source_label'], properties={}, node_id=source_id)
                store.graph.add_node(edge['target_label'], properties={}, node_id=target_id)
                store.graph.add_edge(source_id, target_id, edge['relation'], edge.get('properties', {}))
                count += 1
            return f"✅ Context ingested successfully. {result.get('synthesis_message')} Created {count} edges in temporal graph."
        except Exception as e:
            return f'❌ Failed to ingest context: {str(e)}'

    @mcp.tool()
    def query_temporal_graph(at_time: str=None) -> str:
        """
            Query the temporal knowledge graph to understand connections between decisions, mistakes, and context.
            Args:
                at_time: Optional ISO timestamp to query the graph state exactly as it was at that time.
            """
        try:
            nodes = store.graph.query_graph(at_time=at_time)
            out = f"📊 **Temporal Graph State** (Time: {at_time or 'NOW'})\n\n"
            out += f'**Nodes ({len(nodes)})**:\n'
            for n in nodes[:10]:
                out += f" - {n.get('label', 'Node')} (ID: {n['id']})\n"
                for e in n.get('edges', [])[:3]:
                    out += f"   └── {e['relation']} --> [{e['target_id']}]\n"
            if len(nodes) > 10:
                out += '   ... (truncated)\n'
            return out
        except Exception as e:
            return f'❌ Failed to query graph: {str(e)}'

