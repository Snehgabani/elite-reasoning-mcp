from typing import List, Dict, Any
from core.persistence.vector_store import HybridGraphStore

class MemoryRetrieval:
    """
    Hybrid search retrieval pipeline mimicking System config.
    bge-small-en-v1.5 embeddings, max 16000 inject tokens.
    """
    def __init__(self, vector_store: HybridGraphStore):
        self.vector_store = vector_store
        self.max_inject_tokens = 16000
        self.max_nodes_per_turn = 6

    def recall(self, query: str, limit: int = None) -> str:
        """
        Recall relevant context for the current query.
        Returns a formatted markdown string of retrieved knowledge.
        """
        if limit is None:
            limit = self.max_nodes_per_turn

        results = self.vector_store.search(query, limit=limit)
        
        if not results:
            return ""

        context_blocks = []
        for res in results:
            source = res.get("source", "Unknown")
            text = res.get("text", "")
            score = res.get("score", 0.0)
            
            # Simulated BM25 + Dense Hybrid weighing could go here
            
            block = f"### Source: {source} (Relevance: {score:.2f})\n{text}\n"
            context_blocks.append(block)

        return "<RETRIEVED_CONTEXT>\n" + "\n".join(context_blocks) + "\n</RETRIEVED_CONTEXT>"
