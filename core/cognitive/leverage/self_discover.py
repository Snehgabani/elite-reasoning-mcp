# src/leverage/self_discover.py
# DeepMind SELF-DISCOVER Framework (Dynamic Reasoning Topologies)

import json
from typing import Dict, List, Any

ATOMIC_REASONING_MODULES = [
    "Critical Thinking (Question premises)",
    "Break Into Subtasks (Decompose problem)",
    "Find Bottleneck (Identify failure point)",
    "Debate Both Sides (Dialectical red-teaming)",
    "Formal Logic & Invariants (Mathematical proof)",
    "Inversion (Munger - invert the problem)",
    "First Principles (Strip down to fundamental truths)"
]

class SelfDiscoverEngine:
    def __init__(self):
        pass

    async def compose_topology(self, task: str) -> Dict[str, Any]:
        """
        Dynamically composes a custom reasoning structure tailored to the task
        using DeepMind's SELF-DISCOVER atomic module composition framework.
        """
        t_lower = task.lower()
        selected_modules = []

        if "debug" in t_lower or "fix" in t_lower or "error" in t_lower:
            selected_modules = [
                "Find Bottleneck (Identify failure point)",
                "First Principles (Strip down to fundamental truths)",
                "Critical Thinking (Question premises)"
            ]
        elif "design" in t_lower or "architecture" in t_lower or "strategy" in t_lower:
            selected_modules = [
                "Break Into Subtasks (Decompose problem)",
                "Inversion (Munger - invert the problem)",
                "Debate Both Sides (Dialectical red-teaming)"
            ]
        else:
            selected_modules = [
                "Break Into Subtasks (Decompose problem)",
                "Critical Thinking (Question premises)",
                "Formal Logic & Invariants (Mathematical proof)"
            ]

        custom_dag = {
            "task": task,
            "selected_atomic_modules": selected_modules,
            "composed_structure": [
                {"step": 1, "module": selected_modules[0], "output_expected": "Formulate core problem & invariants"},
                {"step": 2, "module": selected_modules[1], "output_expected": "Execute targeted deduction & reduction"},
                {"step": 3, "module": selected_modules[2], "output_expected": "Stress-test assumptions & finalize solution"}
            ]
        }
        return custom_dag

async def compose_reasoning_topology(task: str) -> str:
    engine = SelfDiscoverEngine()
    res = await engine.compose_topology(task)
    return json.dumps(res, indent=2)
