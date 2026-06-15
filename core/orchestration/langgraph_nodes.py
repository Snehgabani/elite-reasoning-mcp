from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, START, StateGraph


class ContextState(TypedDict):
    raw_text: str
    extracted_entities: List[Dict[str, Any]]
    graph_edges_to_create: List[Dict[str, Any]]
    synthesis_message: str

def extract_entities(state: ContextState) -> Dict[str, Any]:
    """
    Extract concepts from raw text.
    In production, this is wired to an LLM via langchain_core.
    For demonstration of the pipeline, we perform basic heuristic extraction.
    """
    text = state["raw_text"]
    entities = []

    # Heuristic mock for extraction
    if "error" in text.lower():
        entities.append({"label": "ErrorContext", "properties": {"summary": text[:50]}})
    if "refactor" in text.lower():
        entities.append({"label": "RefactorEvent", "properties": {"summary": text[:50]}})

    if not entities:
        entities.append({"label": "GeneralContext", "properties": {"snippet": text[:50]}})

    return {"extracted_entities": entities}

def traverse_and_link(state: ContextState) -> Dict[str, Any]:
    """
    Look up existing nodes in the GraphStore and propose edges.
    """
    edges = []
    for entity in state.get("extracted_entities", []):
        edges.append({
            "source_label": "ContextSession",
            "target_label": entity["label"],
            "relation": "DISCOVERED_IN",
            "properties": {}
        })
    return {"graph_edges_to_create": edges}

def synthesize(state: ContextState) -> Dict[str, Any]:
    """
    Summarize what was ingested.
    """
    count = len(state.get("extracted_entities", []))
    msg = f"Successfully extracted {count} entities and linked them via LangGraph background process."
    return {"synthesis_message": msg}

def build_ingestion_graph() -> StateGraph:
    """Compiles and returns the LangGraph application."""
    workflow = StateGraph(ContextState)

    workflow.add_node("extract", extract_entities)
    workflow.add_node("link", traverse_and_link)
    workflow.add_node("synthesize", synthesize)

    workflow.add_edge(START, "extract")
    workflow.add_edge("extract", "link")
    workflow.add_edge("link", "synthesize")
    workflow.add_edge("synthesize", END)

    return workflow.compile()
