from pathlib import Path
from typing import Dict, Any, List, Optional
import datetime
from core.persistence.file_store import FileStore
from core.persistence.vector_store import HybridGraphStore

class MemoryManager:
    """
    Implements MemGPT/Letta/Zep OS-level paging architecture for Memory.
    
    Core Memory (Always In-Context):
        - Tier 1: Identity / Essentials (Who am I, core rules)
        - Tier 2: Threads (Current goals, active tasks)
        - Tier 3: Recent (Recent working state)
        
    Archival Memory (Out-of-Context, retrieved via paging/vector search):
        - Tier 4: Buffer (Raw event stream)
        - Concepts (Knowledge graph nodes)
        - Decisions (Historical rationale)
    """
    def __init__(self, brain_dir: str, vector_store: HybridGraphStore):
        self.brain_dir = Path(brain_dir)
        self.file_store = FileStore(brain_dir)
        self.vector_store = vector_store
        
        # Ensure memory directories exist
        (self.brain_dir / "memory" / "concepts").mkdir(parents=True, exist_ok=True)
        (self.brain_dir / "memory" / "decisions").mkdir(parents=True, exist_ok=True)
        (self.brain_dir / "memory" / "archival").mkdir(parents=True, exist_ok=True)

    def get_core_context(self) -> str:
        """Retrieve Core Memory block. This is the OS 'RAM' that is always injected."""
        essentials = self.file_store.read("memory/essentials.md") or ""
        threads = self.file_store.read("memory/threads.md") or ""
        recent = self.file_store.read("memory/recent.md") or ""
        
        return f"""
<CORE_MEMORY>
=== essentials.md ===
{essentials}

=== threads.md ===
{threads}

=== recent.md ===
{recent}
</CORE_MEMORY>
"""

    def remember(self, observation: str) -> None:
        """
        Tier 4: Event stream logger. Appends to temporal buffer.
        Acts as the episodic memory ingestion layer.
        """
        timestamp = datetime.datetime.now(datetime.UTC).isoformat()
        formatted_obs = f"[{timestamp}] - {observation}\n"
        self.file_store.append("memory/buffer.md", formatted_obs)

    def search_archival_memory(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Paging function for Archival Memory (concepts/decisions).
        Simulates Letta/Zep archival search via semantic vector similarity.
        """
        results = self.vector_store.search(query, limit=limit)
        return results

    def get_temporal_context(self, start_time: str, end_time: str) -> List[str]:
        """
        Simulates Zep's temporal graph retrieval / Letta paging.
        Reads the episodic buffer and filters by timestamp.
        """
        buffer_content = self.file_store.read("memory/buffer.md") or ""
        lines = buffer_content.strip().split("\n")
        
        events = []
        for line in lines:
            if not line.startswith("["):
                continue
            # Format: [2026-06-12T03:19:19.123456] - Observation
            parts = line.split("]", 1)
            if len(parts) == 2:
                ts = parts[0][1:]
                if start_time <= ts <= end_time:
                    events.append(line)
        return events

    def read_concept(self, concept_name: str) -> str:
        """Read a specific concept page from the structured knowledge graph."""
        content = self.file_store.read(f"memory/concepts/{concept_name}.md")
        return content if content else f"Concept '{concept_name}' not found."

    def write_concept(self, concept_name: str, content: str) -> None:
        """Write or update a concept page and its vector embedding."""
        self.file_store.write(f"memory/concepts/{concept_name}.md", content)
        # Vectorize for archival search
        self.vector_store.add_texts(
            [content], 
            metadatas=[{
                "source": concept_name, 
                "type": "concept",
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
            }]
        )
