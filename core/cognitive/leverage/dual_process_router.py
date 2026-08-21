# src/leverage/dual_process_router.py
# Dual-Process Cognitive Router (Kahneman System 1 / System 2 Theory)

import json
from typing import Any, Dict


class DualProcessRouter:
    def __init__(self):
        pass

    async def classify_task(self, task: str) -> Dict[str, Any]:
        """
        Classifies task into System 1 (Fast heuristic retrieval) or System 2 (Slow deliberate DAG compute).
        """
        t_lower = task.lower().strip()
        words = t_lower.split()

        # Simple single-word, greeting, or direct lookup -> System 1
        if len(words) <= 3 and any(w in t_lower for w in ["hi", "hello", "thanks", "ping", "version", "help"]):
            return {
                "system": "SYSTEM_1",
                "reason": "Simple query / greeting — fast pre-attentive System 1 retrieval",
                "estimated_latency_ms": 50,
                "deep_dag_required": False,
            }

        # Multi-file, strategic, research, refactor, or complex task -> System 2
        return {
            "system": "SYSTEM_2",
            "reason": "Complex cognitive task — requires deliberate System 2 DAG reasoning, PRMs, and web research",
            "estimated_latency_ms": 1500,
            "deep_dag_required": True,
        }


async def dual_process_route(task: str) -> str:
    router = DualProcessRouter()
    res = await router.classify_task(task)
    return json.dumps(res, indent=2)
