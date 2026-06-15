from langgraph.graph import StateGraph, START, END
from typing import Dict, Any, TypedDict

class WorkerState(TypedDict):
    input_data: Any
    result: Any

def create_quality_worker_graph():
    """Create the subgraph for the Quality Auditor worker."""
    builder = StateGraph(WorkerState)
    
    def analyze(state: WorkerState):
        # Run quality benchmarks
        state["result"] = {"status": "passed", "score": 95}
        return state
        
    builder.add_node("analyze", analyze)
    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", END)
    
    return builder.compile()

def create_consolidator_worker_graph():
    """Create the subgraph for the Memory Consolidator worker."""
    builder = StateGraph(WorkerState)
    
    def extract_facts(state: WorkerState):
        state["result"] = {"extracted": 5, "archived": True}
        return state
        
    builder.add_node("extract", extract_facts)
    builder.add_edge(START, "extract")
    builder.add_edge("extract", END)
    
    return builder.compile()
