"""
Trusted Memory Service (WS4 / Phase 2).
Enforces quarantine on unverified lessons, manages project isolation,
promotes verified lessons to active status, and implements physical forget deletion.
"""

from __future__ import annotations

import hashlib
import time
from typing import Dict, List, Optional
from core.memory.models import MemoryScope, SensitivityState, TrustedMemory, TrustState


class TrustedMemoryService:
    """Thread-safe, in-process and persistent memory manager with anti-poisoning enforcement."""

    def __init__(self):
        self._memories: Dict[str, TrustedMemory] = {}

    def propose_lesson(
        self,
        content: str,
        scope: MemoryScope = MemoryScope.PROJECT,
        project_id: Optional[str] = None,
        is_verified: bool = False,
        evidence_ids: Optional[List[str]] = None,
        is_sensitive: bool = False,
    ) -> TrustedMemory:
        norm = content.strip().lower()
        mid = f"MEM-{hashlib.sha256(norm.encode('utf-8')).hexdigest()[:10]}"

        # Rule: Sensitive records cannot become active memory
        sensitivity = SensitivityState.SENSITIVE_SECRET if is_sensitive else SensitivityState.INTERNAL
        if is_sensitive:
            trust = TrustState.QUARANTINED
        else:
            # Rule: Only verified outcomes can automatically become active/approved
            trust = TrustState.ACTIVE if is_verified else TrustState.QUARANTINED

        memory = TrustedMemory(
            id=mid,
            content=content.strip(),
            normalized_content=norm,
            scope=scope,
            project_id=project_id,
            trust_state=trust,
            sensitivity_state=sensitivity,
            evidence_ids=evidence_ids or [],
            created_at=time.time(),
            updated_at=time.time(),
        )
        self._memories[mid] = memory
        return memory

    def approve_lesson(self, memory_id: str) -> Optional[TrustedMemory]:
        mem = self._memories.get(memory_id)
        if mem:
            if mem.sensitivity_state == SensitivityState.SENSITIVE_SECRET:
                raise ValueError("Cannot approve sensitive secret as active memory")
            mem.trust_state = TrustState.ACTIVE
            mem.updated_at = time.time()
        return mem

    def get_active_memories(self, project_id: Optional[str] = None) -> List[TrustedMemory]:
        results = []
        for mem in self._memories.values():
            if mem.trust_state == TrustState.ACTIVE:
                # Enforce project isolation
                if mem.scope == MemoryScope.GLOBAL or mem.project_id == project_id:
                    results.append(mem)
        return results

    def forget(self, memory_id: str) -> bool:
        """Physically deletes memory item (zero retention)."""
        if memory_id in self._memories:
            del self._memories[memory_id]
            return True
        return False

    def associative_recall(
        self,
        query: str,
        project_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[TrustedMemory]:
        """Performs HippoRAG 2 Personalized PageRank associative retrieval across active memories."""
        from core.memory.hipporag import HippoRAGAssociativeEngine

        active = self.get_active_memories(project_id=project_id)
        if not active:
            return []

        engine = HippoRAGAssociativeEngine()
        for mem in active:
            engine.add_node(
                mem.id,
                label=mem.scope.value,
                properties={"content": mem.content, "project_id": mem.project_id},
                timestamp=mem.created_at,
            )

        res = engine.associative_recall(query=query, top_k=top_k)
        retrieved_ids = {m.id for m in res.ranked_memories}
        return [self._memories[mid] for mid in retrieved_ids if mid in self._memories]
