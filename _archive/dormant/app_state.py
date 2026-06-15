from typing import TypedDict, Annotated, Sequence, Dict, Any, List
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    Main LangGraph State schema.
    Channels represent the data streams the assistant manages.
    """
    # Conversation history (Append-only reducer)
    messages: Annotated[Sequence, add_messages]
    
    # Structural OODA Telemetry
    ooda_diagnostic: str
    
    # Pre-flight classification results
    intent_class: str
    framework_stack: List[str]
    confidence_cap: float
    recall_needed: bool
    hard_stop: bool
    
    # Retrieved context
    memory_context: str
    
    # Reasoning execution results
    reasoning_output: Dict[str, Any]
    
    # FMEA score for the final action
    fmea_score: int
    
    # Tool infinite loop protection
    tool_retry_count: int
