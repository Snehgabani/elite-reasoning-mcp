from langgraph.graph import StateGraph, START, END
from typing import Dict, Any, List, TypedDict

class SupervisorState(TypedDict):
    task: str
    workers_completed: List[str]
    final_output: str
    
class SwarmSupervisor:
    """
    LangGraph Supervisor pattern for the Swarm.
    Routes tasks to specialized worker subgraphs.
    """
    def __init__(self):
        self.builder = StateGraph(SupervisorState)
        self._build_graph()
        self.graph = self.builder.compile()

    def _build_graph(self):
        # Add nodes
        self.builder.add_node("router", self._router_node)
        self.builder.add_node("worker_quality", self._quality_worker)
        self.builder.add_node("worker_consolidator", self._consolidator_worker)
        self.builder.add_node("synthesize", self._synthesize)

        # Edges
        self.builder.add_edge(START, "router")
        self.builder.add_conditional_edges(
            "router",
            self._route_decision,
            {
                "quality": "worker_quality",
                "consolidate": "worker_consolidator",
                "done": "synthesize"
            }
        )
        self.builder.add_edge("worker_quality", "router")
        self.builder.add_edge("worker_consolidator", "router")
        self.builder.add_edge("synthesize", END)

    def _router_node(self, state: SupervisorState):
        """Supervisor decides what to do next."""
        return state

    def _route_decision(self, state: SupervisorState) -> str:
        """Condition function for routing."""
        if "quality" not in state["workers_completed"] and "audit" in state["task"]:
            return "quality"
        if "consolidate" not in state["workers_completed"] and "memory" in state["task"]:
            return "consolidate"
        return "done"
        
    def _quality_worker(self, state: SupervisorState):
        """Delegates to the quality auditor worker."""
        state["workers_completed"].append("quality")
        return state
        
    def _consolidator_worker(self, state: SupervisorState):
        """Delegates to the memory consolidator worker."""
        state["workers_completed"].append("consolidate")
        return state

    def _synthesize(self, state: SupervisorState):
        """Synthesize final output."""
        state["final_output"] = f"Processed {state['task']} via {state['workers_completed']}"
        return state
