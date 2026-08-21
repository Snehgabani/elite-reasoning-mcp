# Honest stub: this package does not run Language Agent Tree Search.
from typing import Any, Dict, List


class LATSNode:
    def __init__(self, state: str, parent=None, depth: int = 0):
        self.state = state
        self.parent = parent
        self.depth = depth
        self.children: List["LATSNode"] = []
        self.visits = 0
        self.reward = 0.0


class LATSSearchEngine:
    def __init__(self, max_branch: int = 2, max_depth: int = 3, max_simulations: int = 8):
        self.max_branch = max_branch
        self.max_depth = max_depth
        self.max_simulations = max_simulations

    async def search(self, task: str) -> Dict[str, Any]:
        return {
            "task": task,
            "simulations": 0,
            "best_score": None,
            "best_state": "",
            "status": "not_a_search",
            "summary": (
                "LATS tree search is not executed here. Generate a real candidate and "
                "call elite_verify(check='tests')."
            ),
            "solution": None,
        }


async def hard_reason(task: str) -> str:
    engine = LATSSearchEngine()
    res = await engine.search(task)
    return f"## LATS not executed\nTask: {task}\n{res['summary']}\nDo not treat this as a solution."
