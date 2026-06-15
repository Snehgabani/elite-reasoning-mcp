from typing import List, Dict, Any, Optional
import uuid
import logging
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None

logger = logging.getLogger(__name__)

class HybridGraphStore:
    """
    Hybrid GraphRAG adapter combining Qdrant (Vector) and Neo4j (Graph).
    Matches System's embedding model: bge-small-en-v1.5 (384-dim).
    """
    def __init__(self, brain_dir: str = None, neo4j_uri: str = "bolt://localhost:7687", neo4j_auth: tuple = ("neo4j", "password")):
        import os
        # We use a lightweight local memory Qdrant for development/testing, or disk if brain_dir is provided
        if brain_dir:
            qdrant_path = os.path.join(brain_dir, "qdrant_storage")
            os.makedirs(qdrant_path, exist_ok=True)
            try:
                self.vector_client = QdrantClient(path=qdrant_path)
            except Exception as e:
                if "Lock" in str(e) or "BlockingIOError" in str(e.__class__.__name__):
                    logger.warning("Qdrant storage is locked by another process. Falling back to memory storage for this session.")
                    self.vector_client = QdrantClient(":memory:")
                else:
                    raise
        else:
            self.vector_client = QdrantClient(":memory:")
            
        self.collection_name = "system_memory"
        self.encoder = SentenceTransformer("BAAI/bge-small-en-v1.5")
        self._init_vector_collection()
        
        # Neo4j Graph client setup
        self.graph_client = None
        if GraphDatabase:
            try:
                self.graph_client = GraphDatabase.driver(neo4j_uri, auth=neo4j_auth)
            except Exception as e:
                logger.warning(f"Neo4j connection failed: {e}. Graph features will be mocked.")
        else:
            logger.warning("neo4j python driver not found. Graph features disabled.")

    def _init_vector_collection(self):
        """Initialize the Qdrant collection if it doesn't exist."""
        if not self.vector_client.collection_exists(collection_name=self.collection_name):
            self.vector_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )

    def add_texts(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """Embed and add texts to the vector store, and optionally insert nodes to Graph."""
        if not texts:
            return []
            
        embeddings = self.encoder.encode(texts)
        ids = [str(uuid.uuid4()) for _ in texts]
        
        points = []
        for i, text in enumerate(texts):
            payload = {"text": text}
            if metadatas and i < len(metadatas):
                payload.update(metadatas[i])
                
            points.append(
                PointStruct(
                    id=ids[i],
                    vector=embeddings[i].tolist(),
                    payload=payload
                )
            )
            
            # Neo4j entity extraction & graph insertion (Stubbed)
            if self.graph_client:
                self._insert_graph_node(ids[i], text, payload)
            
        self.vector_client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        return ids

    def _insert_graph_node(self, node_id: str, text: str, metadata: dict):
        """Extract entities and insert into Neo4j graph using Cypher."""
        if not self.graph_client:
            return
            
        # Simplified Concept node insertion for GraphRAG
        # In a real system, you'd run LLM extraction here to build complex relationships
        concept_type = metadata.get("type", "Concept")
        source = metadata.get("source", "unknown")
        
        query = """
        MERGE (c:Concept {id: $id})
        SET c.text = $text, c.type = $type, c.source = $source
        """
        try:
            with self.graph_client.session() as session:
                session.run(query, id=node_id, text=text, type=concept_type, source=source)
        except Exception as e:
            logger.error(f"Failed to insert graph node: {e}")

    def search(self, query: str, limit: int = 5, start_time: Optional[str] = None, end_time: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Hybrid search for similar texts.
        Queries Qdrant for semantic similarity, then optionally augments with Graph traversal.
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        # 1. Vector Search
        query_vector = self.encoder.encode(query).tolist()
        
        # We'll do post-filtering for temporal since Qdrant string ranges require specific indexes
        # In a production system, we'd use zep-python or proper Qdrant datetime indexing
        search_result = self.vector_client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit * 3 if (start_time or end_time) else limit
        ).points
        
        results = []
        for hit in search_result:
            timestamp = hit.payload.get("timestamp", "")
            
            # Temporal filter
            if start_time and timestamp < start_time:
                continue
            if end_time and timestamp > end_time:
                continue
                
            result = {
                "score": hit.score,
                "text": hit.payload.get("text", "")
            }
            for k, v in hit.payload.items():
                if k != "text":
                    result[k] = v
                    
            # 2. Graph Augmentation (GraphRAG logic)
            if self.graph_client:
                # Query neo4j for related nodes based on result ID
                graph_context = self._query_graph_relationships(hit.id)
                if graph_context:
                    result["graph_context"] = graph_context
                    
            results.append(result)
            
            if len(results) >= limit:
                break
            
        return results

    def _query_graph_relationships(self, node_id: str) -> str:
        """Fetch multi-hop context from the graph database."""
        if not self.graph_client:
            return ""
            
        # Cypher query to fetch 1-hop connected concepts
        query = """
        MATCH (c:Concept {id: $id})-[r]-(connected)
        RETURN type(r) as rel_type, connected.text as text, connected.type as type
        LIMIT 5
        """
        try:
            with self.graph_client.session() as session:
                result = session.run(query, id=node_id)
                context = []
                for record in result:
                    context.append(f"- ({record['type']}) {record['text']} [via {record['rel_type']}]")
                return "\n".join(context)
        except Exception as e:
            logger.error(f"Failed to query graph: {e}")
            return ""
