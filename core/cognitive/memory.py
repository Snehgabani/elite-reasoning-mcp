# src/memory.py
# This file wires Cognee's persistent knowledge graph into the agent.
# Cognee provides: permanent graph memory + fast session cache.

import warnings
warnings.filterwarnings("ignore")

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────
# MEMORY TOOL FACTORY
# Returns two tools: add_memory_tool + search_memory_tool
# These are attached to the agent as callable tools.
# ─────────────────────────────────────────────

def get_memory_tools(session_id: str = "default-session"):
    """
    Returns (add_tool, search_tool) for this session.
    session_id: use project name or user ID for isolation.
    """
    try:
        from cognee_integration_langgraph import get_sessionized_cognee_tools
        return get_sessionized_cognee_tools(session_id)
    except Exception:
        return None, None


# ─────────────────────────────────────────────
# MEMORY WRITER
# Call this after EVERY successful task completion.
# Saves the reasoning trace into permanent memory.
# ─────────────────────────────────────────────

async def save_reasoning_trace(
    task: str,
    reasoning_graph: dict,
    outcome: str,
    session_id: str = "default-session"
):
    """
    Writes a completed reasoning trace to Cognee's permanent graph.
    This is what makes the system get smarter over time.
    
    Args:
        task: the original task string
        reasoning_graph: dict with all nodes from ReasoningState
        outcome: "success" or "failure"
        session_id: isolates memory per project
    """
    import cognee
    
    # Format the trace as structured text for graph extraction
    trace_text = f"""
TASK: {task}
OUTCOME: {outcome}
PLAN: {'; '.join(reasoning_graph.get('plan_nodes', []))}
FACTS: {'; '.join(reasoning_graph.get('fact_nodes', []))}
REASONING: {'; '.join(reasoning_graph.get('reason_nodes', []))}
CONCLUSION: {reasoning_graph.get('conclude_node', 'none')}
BACKTRACKS: {reasoning_graph.get('backtrack_count', 0)}
"""
    # Add to session cache (fast), then sync to permanent graph
    await cognee.add(trace_text, dataset_name=f"session-{session_id}")
    await cognee.cognify()  # This triggers graph extraction and storage


# ─────────────────────────────────────────────
# SKILL LOADER
# Reads all .md files from .ai/skills/ and .ai/primitives/
# Returns them as a list of text strings.
# ─────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_skill_library() -> list[str]:
    """
    Loads all skill files and primitives from the .ai directory.
    Call this once at agent startup.
    """
    import glob
    skills = []
    
    primitives_pattern = os.path.join(PROJECT_ROOT, ".ai", "primitives", "*.md")
    for filepath in glob.glob(primitives_pattern):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                skills.append(f"PRIMITIVE [{filepath}]:\n" + f.read())
        except Exception as e:
            # Suppress expected non-fatal exception
            pass
    
    skills_pattern = os.path.join(PROJECT_ROOT, ".ai", "skills", "*.md")
    for filepath in glob.glob(skills_pattern):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                skills.append(f"SKILL [{filepath}]:\n" + f.read())
        except Exception as e:
            # Suppress expected non-fatal exception
            pass
    
    return skills


# ─────────────────────────────────────────────
# REASONING PROTOCOL LOADER
# Loads the XML protocol from .ai/system/
# ─────────────────────────────────────────────

def load_reasoning_protocol() -> str:
    """Loads the global reasoning protocol XML."""
    protocol_path = os.path.join(PROJECT_ROOT, ".ai", "system", "reasoning_protocol.xml")
    if os.path.exists(protocol_path):
        with open(protocol_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<reasoning_protocol></reasoning_protocol>"

