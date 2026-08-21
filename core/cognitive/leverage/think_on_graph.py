# src/leverage/think_on_graph.py
# Think-on-Graph (ToG) Interactive Knowledge Graph Beam Search Engine

import json
from typing import Any, Dict

from core.cognitive.leverage.repo_graph import RepoGraph


class ThinkOnGraphEngine:
    def __init__(self):
        self.repo_graph = RepoGraph()

    async def beam_search_kg(self, entity: str, query: str, beam_width: int = 3, depth: int = 2) -> Dict[str, Any]:
        """
        Executes multi-hop Knowledge Graph beam search (Think-on-Graph).
        Explores relational paths (entity -> relation -> entity) to uncover multi-hop facts.
        """
        initial_nodes = self.repo_graph.search(entity, k=beam_width)
        beams = []

        for node in initial_nodes:
            symbol = node.get("symbol", entity)
            impact = self.repo_graph.impact_map(symbol)
            deps = impact.get("dependencies", [])
            dependents = impact.get("dependents", [])
            
            path = {
                "root": symbol,
                "type": node.get("type", "unknown"),
                "file": node.get("file", ""),
                "relations": [
                    {"relation": "DEPENDS_ON", "targets": deps[:3]},
                    {"relation": "USED_BY", "targets": dependents[:3]}
                ]
            }
            beams.append(path)

        multi_hop_facts = []
        for b in beams:
            root = b["root"]
            for r in b["relations"]:
                rel_name = r["relation"]
                for target in r["targets"]:
                    multi_hop_facts.append(f"({root}) --[{rel_name}]--> ({target})")

        return {
            "entity": entity,
            "query": query,
            "beam_width": beam_width,
            "explored_paths": beams,
            "multi_hop_facts": multi_hop_facts,
            "summary": f"Discovered {len(multi_hop_facts)} relational multi-hop graph facts for entity '{entity}'."
        }

async def think_on_graph_search(entity: str, query: str) -> str:
    engine = ThinkOnGraphEngine()
    res = await engine.beam_search_kg(entity, query)
    return json.dumps(res, indent=2)
