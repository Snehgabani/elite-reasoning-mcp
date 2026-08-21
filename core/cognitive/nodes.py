# src/nodes.py
# Phase 14 Ironclad Closed-Loop ReasoningState Schema
# Enforces strict typing, zero-escape control flags, and bounded recursion.

from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langgraph.graph.message import add_messages


class ReasoningState(TypedDict):
    """
    The shared state notebook that every node reads from and writes to.
    Every field here persists across ALL nodes in the graph.
    """

    # ── 1. Core Task Specification ──────────────────────────────────
    task: str  # The original user task
    task_type: str  # debug / architecture / algorithm / review / general
    cognitive_system: str  # SYSTEM_1 (fast path) / SYSTEM_2 (deep graph)

    # ── 2. Decomposition & Research State ──────────────────────────
    plan_nodes: List[str]  # Subproblems produced by planner
    fact_nodes: List[str]  # Verified facts
    research_nodes: List[str]  # Live web triangulation citations
    red_team_nodes: List[str]  # Dialectical antithesis attacks
    synthesis_node: Optional[str]  # Hegelian synthesis defense
    mental_models: List[str]  # Selected mental models
    self_discover_topology: Optional[dict]  # Dynamic topology
    tog_facts: List[str]  # Think-on-Graph facts
    self_rag_reflection: Optional[dict]  # Self-RAG reflection tokens
    assume_nodes: List[str]  # Flagged assumptions
    example_nodes: List[str]  # Exemplars

    # ── 3. Code Generation & Diff Proposals ─────────────────────────
    reason_nodes: List[str]  # Logical deduction steps
    code_blocks: List[str]  # Extracted code blocks
    code_candidate: str  # Active synthesized code or patch
    proposed_diff: Optional[Dict[str, Any]]  # Structured diff: {"file_path", "original", "replacement"}

    # ── 4. Deterministic Invariant & Gating State ───────────────────
    prm_step_scores: List[float]  # Historical PRM step scores
    prm_score: float  # Current candidate PRM score (0.0 .. 1.0)
    prm_passed: bool  # Invariant gate pass status
    blocking_issues: List[str]  # Specific syntax/invariant errors to fix
    reflect_confidence: str  # HIGH / MED / LOW

    # ── 5. Zero-Escape Control Flow & Execution ─────────────────────
    retry_count: int  # Monotonic integer counter (0..3)
    backtrack_count: int  # Historical backtrack count
    current_branch: int  # Active branch index
    iteration_count: int  # Safety cycle counter
    gated_token: Optional[str]  # Single-use HMAC authorization nonce
    execution_status: str  # PENDING / EXECUTED / ESCALATED / COMPLETED
    execution_results: List[str]  # Execution logs from tools / disk writes
    execution_result: Optional[str]  # Primary execution summary
    conclude_node: Optional[str]  # Synthesized conclusion
    final_answer: Optional[str]  # Final response delivered to caller

    # ── 6. Memory & Telemetry ───────────────────────────────────────
    relevant_skills: List[str]  # Skills retrieved from store
    relevant_facts: List[str]  # Facts retrieved from store
    failed_branch_summaries: List[str]  # Summaries of failed branches
    messages: Annotated[List, add_messages]  # Message history
    next_action: str  # Next routing directive
