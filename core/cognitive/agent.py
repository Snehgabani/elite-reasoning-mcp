# src/agent.py
# Phase 14 Ironclad Cognitive Singularity Graph Assembly
# Enforces closed-loop PRM verification, physical disk barriers, and bounded recursion.

import os
import sys
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from core.cognitive.nodes import ReasoningState
from core.cognitive.agent_nodes import (
    cognitive_router_node,
    self_discover_node,
    planner_node,
    think_on_graph_node,
    research_node,
    fact_node,
    epistemic_verifier_node,
    self_rag_node,
    reason_node,
    prm_gate_node,
    reflexion_node,
    deterministic_executor_node,
    escalation_node,
    red_team_node,
    reflect_node,
    executor_node,
    conclude_node,
    backtrack_node,
)


def route_after_prm_gate(state: ReasoningState) -> str:
    """
    Zero-Escape Invariant Routing Edge:
    - If prm_passed is True -> proceed to deterministic executor.
    - If prm_passed is False and retry_count < 3 -> loop to reflexion repair.
    - If prm_passed is False and retry_count >= 3 -> cleanly halt at escalation node.
    """
    if state.get("prm_passed", False):
        return "deterministic_executor"
    if state.get("retry_count", 0) < 3:
        return "reflexion"
    return "escalation"


def route_after_router(state: ReasoningState) -> str:
    """Fast bypass for System 1 read-only queries."""
    if state.get("cognitive_system") == "SYSTEM_1":
        return "conclude"
    return "self_discover"


def build_reasoning_graph():
    """Compiles and returns the ironclad closed-loop LangGraph application."""
    graph = StateGraph(ReasoningState)

    # ── Register All Nodes ──────────────────────────────────────────
    graph.add_node("cognitive_router",       cognitive_router_node)
    graph.add_node("self_discover",          self_discover_node)
    graph.add_node("plan",                   planner_node)
    graph.add_node("think_on_graph",         think_on_graph_node)
    graph.add_node("research",               research_node)
    graph.add_node("fact",                   fact_node)
    graph.add_node("epistemic_verifier",     epistemic_verifier_node)
    graph.add_node("self_rag",               self_rag_node)
    graph.add_node("reason",                 reason_node)
    graph.add_node("prm_gate",               prm_gate_node)
    graph.add_node("reflexion",              reflexion_node)
    graph.add_node("deterministic_executor", deterministic_executor_node)
    graph.add_node("escalation",             escalation_node)
    graph.add_node("red_team",               red_team_node)
    graph.add_node("reflect",                reflect_node)
    graph.add_node("conclude",               conclude_node)

    # ── Pipeline Routing ────────────────────────────────────────────
    graph.add_edge(START, "cognitive_router")
    
    # System 1 / System 2 dynamic routing
    graph.add_conditional_edges(
        "cognitive_router",
        route_after_router,
        {
            "conclude": "conclude",
            "self_discover": "self_discover"
        }
    )

    graph.add_edge("self_discover",      "plan")
    graph.add_edge("plan",               "think_on_graph")
    graph.add_edge("think_on_graph",     "research")
    graph.add_edge("research",           "fact")
    graph.add_edge("fact",               "epistemic_verifier")
    graph.add_edge("epistemic_verifier", "self_rag")
    graph.add_edge("self_rag",           "reason")
    graph.add_edge("reason",             "prm_gate")

    # The Zero-Escape Invariant Gate Edge
    graph.add_conditional_edges(
        "prm_gate",
        route_after_prm_gate,
        {
            "deterministic_executor": "deterministic_executor",
            "reflexion":              "reflexion",
            "escalation":             "escalation"
        }
    )

    # Closed-loop Reflexion cycle back to reasoner
    graph.add_edge("reflexion",              "reason")

    # Post-execution dialectical stress testing & synthesis
    graph.add_edge("deterministic_executor", "red_team")
    graph.add_edge("red_team",               "reflect")
    graph.add_edge("reflect",                "conclude")
    graph.add_edge("escalation",             "conclude")
    graph.add_edge("conclude",               END)

    checkpointer = MemorySaver()
    app = graph.compile(checkpointer=checkpointer)
    return app
