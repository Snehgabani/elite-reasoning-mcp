"""
Sovereign Vector Memory Bridge.
Interfaces with ~/.local/bin/sovereign-search (sqlite-vec + FastEmbed bge-small-en-v1.5)
for in-process semantic memory indexing and vector search (<10MB RAM).
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, Optional


SOVEREIGN_SEARCH_BIN = os.path.expanduser("~/.local/bin/sovereign-search")
SOVEREIGN_MEMORY_DIR = os.path.expanduser("~/.elite-reasoning/brain/vector_skills")


class VectorMemoryBridge:
    """
    Manages semantic skill indexing and retrieval via sovereign-search.
    """

    def __init__(self, binary_path: Optional[str] = None):
        self.bin_path = binary_path or (SOVEREIGN_SEARCH_BIN if os.path.exists(SOVEREIGN_SEARCH_BIN) else None)
        os.makedirs(SOVEREIGN_MEMORY_DIR, exist_ok=True)

    def index_skill(self, skill_name: str, pattern: str, invariant_rule: str) -> Dict[str, Any]:
        """
        Saves skill card to memory directory and indexes it with sovereign-search.
        """
        file_name = f"{skill_name.lower().replace(' ', '_')}.md"
        file_path = os.path.join(SOVEREIGN_MEMORY_DIR, file_name)

        content = f"# Skill: {skill_name}\n\n## Pattern\n{pattern}\n\n## Invariant Rule\n{invariant_rule}\n"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        if not self.bin_path:
            return {
                "status": "SAVED_LOCAL_ONLY",
                "file_path": file_path,
                "vector_engine": "NOT_CONFIGURED",
            }

        try:
            res = subprocess.run(
                [self.bin_path, "index", file_path],
                capture_output=True,
                text=True,
                timeout=15.0,
                check=False,
            )
            return {
                "status": "INDEXED" if res.returncode == 0 else "INDEX_ERROR",
                "file_path": file_path,
                "stdout": res.stdout.strip(),
                "vector_engine": "sqlite-vec",
            }
        except Exception as exc:
            return {
                "status": "INDEX_ERROR",
                "file_path": file_path,
                "error": str(exc),
            }

    def search_skills(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """
        Queries sovereign-search for semantically relevant skill cards.
        """
        if not self.bin_path:
            return {
                "status": "UNAVAILABLE",
                "query": query,
                "results": [],
                "error": "sovereign-search binary not found",
            }

        try:
            res = subprocess.run(
                [self.bin_path, "search", query],
                capture_output=True,
                text=True,
                timeout=15.0,
                check=False,
            )
            return {
                "status": "SUCCESS",
                "query": query,
                "raw_output": res.stdout.strip(),
                "vector_engine": "sqlite-vec",
            }
        except Exception as exc:
            return {
                "status": "SEARCH_ERROR",
                "query": query,
                "error": str(exc),
            }


_VECTOR_MEMORY_BRIDGE = VectorMemoryBridge()

__all__ = ["VectorMemoryBridge", "_VECTOR_MEMORY_BRIDGE", "SOVEREIGN_SEARCH_BIN", "SOVEREIGN_MEMORY_DIR"]
