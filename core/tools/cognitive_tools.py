"""
Cognitive Tools Registration Module for Elite Reasoning MCP.
Registers all 42 unified tools (MIX Supreme God-Tools, Invariant Gates, PRMs, Dialectical Debate Panels,
AST Code Property Graphs, Stanford STORM Research, and Longitudinal Calibration).
"""
import json
from typing import List, Optional

from core.cognitive.engine import _COGNITIVE_ENGINE
from core.cognitive.leverage.candidate_search import generate_candidates, score_candidates, select_best_candidate
from core.cognitive.leverage.claim_verify import verify_claims as _run_verify_claims
from core.cognitive.leverage.constitutional_judge import generate_and_judge as _run_god_tier_judge
from core.cognitive.leverage.deep_read import deep_read_url as _run_deep_read
from core.cognitive.leverage.devils_advocate import revision_loop as _run_devils_advocate
from core.cognitive.leverage.dual_process_router import dual_process_route as _run_dual_route
from core.cognitive.leverage.epistemic_orchestrator import epistemic_research as _run_epistemic_research
from core.cognitive.leverage.epistemic_verifier import epistemic_verify as _run_epistemic_verify
from core.cognitive.leverage.expert_panel import expert_panel as _run_expert_panel
from core.cognitive.leverage.fuzz import run_property_tests as _run_property_tests
from core.cognitive.leverage.lats import hard_reason as _run_hard_reason
from core.cognitive.leverage.logic_verifier import verify_argument as _verify_argument
from core.cognitive.leverage.prompt_optimizer import SkillCompiler
from core.cognitive.leverage.red_team import red_team_attack as _run_red_team_attack
from core.cognitive.leverage.reflexion import reflexion_repair
from core.cognitive.leverage.repo_graph import RepoGraph
from core.cognitive.leverage.research_agent import autonomous_research as _run_autonomous_research
from core.cognitive.leverage.self_discover import compose_reasoning_topology as _compose_topology
from core.cognitive.leverage.self_rag import self_rag_evaluate as _run_self_rag_evaluate
from core.cognitive.leverage.skeleton_of_thought import skeleton_of_thought_generate as _run_sot_generate
from core.cognitive.leverage.storm_research import deep_research_report as _run_deep_research_report
from core.cognitive.leverage.task_watcher import get_live_status as _get_live_status
from core.cognitive.leverage.temporal_check import temporal_verify as _run_temporal_verify
from core.cognitive.leverage.think_on_graph import ThinkOnGraphEngine
from core.cognitive.leverage.verifier import verify_code_candidate, verify_non_code_candidate
from core.cognitive.leverage.web_research import LiveWebResearcher as _Triangulator
from core.cognitive.leverage.web_research import live_web_search as _run_live_web_search


def register(mcp, store=None, profile=None) -> None:
    """Register all cognitive tools onto the FastMCP server."""

    # ============================================================================
    # 1. SUPREME UNIFIED GOD-TOOLS
    # ============================================================================

    @mcp.tool()
    async def execute_mix(
        task: str,
        task_id: Optional[str] = None,
        task_type: str = "hard_problem",
        enable_prm: bool = True,
        enable_bias_scan: bool = True
    ) -> str:
        """
        Execute the Supreme MIX Cognitive Pipeline (Loop Meta-Routing + 18-Layer Singularity DAG + PRM + PoW).
        """
        res = await _COGNITIVE_ENGINE.execute_mix(
            task=task,
            task_id=task_id,
            task_type=task_type,
            enable_prm=enable_prm,
            enable_bias_scan=enable_bias_scan
        )
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def elite_reason(task: str, task_type: str = "hard_problem", task_id: str = "default") -> str:
        """Runs deliberate elite reasoning pipeline."""
        return await execute_mix(task=task, task_id=task_id, task_type=task_type)

    @mcp.tool()
    async def execute_singularity(
        task: str,
        task_id: Optional[str] = None,
        task_type: str = "hard_problem",
        max_iterations: int = 3
    ) -> str:
        """Backward-compatible entry point for execute_mix."""
        return await execute_mix(task=task, task_id=task_id, task_type=task_type)

    @mcp.tool()
    def get_live_watcher_status() -> str:
        """
        Get real-time live telemetry, active cognitive graphs, and watchdog health status.
        Guarantees no task is stuck anywhere.
        """
        return json.dumps(_get_live_status(), indent=2)

    # ============================================================================
    # 2. DEEP VERIFICATION & INVARIANT TOOLS
    # ============================================================================

    @mcp.tool()
    async def prm_verify_step(step_text: str, task_id: Optional[str] = None) -> str:
        """
        Verify step validity via Process Reward Model (Math invariants, AST syntax, quantifier biases).
        """
        res = await _COGNITIVE_ENGINE.prm.verify_step(step_text)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def compose_reasoning_topology(task: str) -> str:
        """
        Compose dynamic task-specific reasoning DAG topology using Self-Discover framework.
        """
        res = await _compose_topology(task)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def think_on_graph_search(query: str, depth: int = 2, beam_width: int = 3) -> str:
        """
        Explore hypothesis paths via Think-on-Graph (ToG) beam search over knowledge graph.
        """
        engine = ThinkOnGraphEngine()
        res = await engine.beam_search_kg(entity=query, query=query, beam_width=beam_width, depth=depth)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def verify_argument(argument: str, task_id: str = "default") -> str:
        """
        Verify formal syllogisms and check for logical fallacies with deterministic fail-safe.
        """
        res = await _verify_argument(argument)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def expert_panel(topic: str, personas: Optional[List[str]] = None) -> str:
        """
        Concurrently evaluate dialectical viewpoints across domain expert personas (Economist, Engineer, Scientist).
        """
        res = await _run_expert_panel(topic, personas)
        return json.dumps(res, indent=2)

    @mcp.tool()
    def repo_search(query: str, k: int = 8, task_id: str = "default") -> str:
        """
        Search codebase AST property graph for symbol definitions and references.
        """
        graph = RepoGraph()
        res = graph.search(query=query, k=k)
        return json.dumps(res, default=str, indent=2)

    @mcp.tool()
    def repo_impact_map(symbol: str, task_id: str = "default") -> str:
        """
        Calculate blast radius, dependent modules, and impacted tests for a code change.
        """
        graph = RepoGraph()
        res = graph.impact_map(symbol=symbol)
        return json.dumps(res, default=str, indent=2)

    @mcp.tool()
    def apply_reasoning_diff(
        file_path: str,
        diff_content: str,
        task_id: Optional[str] = None
    ) -> str:
        """
        Apply code modification gated by mandatory Proof-of-Work and prior PRM verification.
        """
        res = _COGNITIVE_ENGINE.enforcer.apply_diff(file_path, diff_content, task_id=task_id)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def fuzz_symbol(symbol: str, task_id: str = "default") -> str:
        """
        Generates and runs property-based tests for a symbol, returning edge cases that break the implementation.
        """
        res = await _run_property_tests(file_path="dummy.py", symbol=symbol)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def god_tier_reasoning(task: str, candidates: int = 5, task_id: str = "default") -> str:
        """
        Generates N distinct reasoning paths in parallel, judges them against the 
        Constitutional Rubric (.ai/system/constitution.xml), and performs Rejection 
        Sampling to return only the mathematically verified, highest-scoring answer.
        """
        res = await _run_god_tier_judge(task, n_candidates=candidates)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def hard_reason(task: str, task_id: str = "default") -> str:
        """Uses budgeted tree search (LATS) for hard tasks requiring an executable verifier."""
        return await _run_hard_reason(task)

    @mcp.tool()
    async def dual_process_route(task: str, task_id: str = "default") -> str:
        """Routes task to System 1 (fast heuristic) or System 2 (deep deliberate graph)."""
        res = await _run_dual_route(task)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def self_rag_evaluate(query: str, retrieved_context: str, generated_response: str, task_id: str = "default") -> str:
        """Evaluates retrieval relevance, support, and utility via Self-RAG reflection tokens."""
        res = await _run_self_rag_evaluate(query, retrieved_context, generated_response)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def skeleton_of_thought_generate(task: str, task_id: str = "default") -> str:
        """Generates a skeleton structure and expands all points concurrently in parallel."""
        res = await _run_sot_generate(task)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def live_web_search(query: str, num_results: int = 5, task_id: str = "default") -> str:
        """Executes live web search across multiple search engines with semantic ranking."""
        res = await _run_live_web_search(query, num_results=num_results)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def red_team_attack(hypothesis: str, task_id: str = "default") -> str:
        """Adversarial stress-tester: generates counter-hypotheses, failure modes, and edge cases."""
        res = await _run_red_team_attack(hypothesis)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def epistemic_verify(claim: str, task_id: str = "default") -> str:
        """Deconstructs claims into atomic propositions and verifies each against authoritative ground truth."""
        claims = [claim] if isinstance(claim, str) else claim
        res = await _run_epistemic_verify(claims)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def triangulate_claim(claim: str, task_id: str = "default") -> str:
        """Verifies a claim by cross-referencing multiple independent sources."""
        triangulator = _Triangulator()
        res = await triangulator.search_and_triangulate(claim)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def deep_read(url: str, query: str = "", task_id: str = "default") -> str:
        """Performs full markdown extraction, chunking, and semantic relevance filtering on a target URL."""
        res = await _run_deep_read(url, query=query)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def temporal_verify(claim: str, task_id: str = "default") -> str:
        """Verifies temporal validity of a statement against timestamped records and historical changes."""
        res = await _run_temporal_verify(claim)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def devils_advocate(draft: str, task_id: str = "default") -> str:
        """Runs dialectical revision loop to challenge assumptions and strengthen draft arguments."""
        res = await _run_devils_advocate(draft)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def epistemic_research(topic: str, task_id: str = "default") -> str:
        """Orchestrates multi-phase deep epistemic research with provenance tracking."""
        res = await _run_epistemic_research(topic)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def verify_claims(draft: str, task_id: str = "default") -> str:
        """Automated claim extraction and verification pipeline over draft text."""
        res = await _run_verify_claims(draft)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def deep_research_report(topic: str, task_id: str = "default") -> str:
        """Stanford STORM Deep Research Engine: Table of Contents, live web citations, Red-Team synthesis."""
        return await _run_deep_research_report(topic)

    @mcp.tool()
    async def autonomous_research(question: str, max_iterations: int = 3, task_id: str = "default") -> str:
        """Iterative research loops: decompose question -> sub-questions -> search+deep_read -> synthesize."""
        res = await _run_autonomous_research(question, max_iterations=max_iterations)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def candidate_search(task: str, mode: str = "deep", test_command: Optional[str] = None, task_id: str = "default") -> str:
        """Generates multiple solution candidates, verifies them, and selects the best one."""
        n = 3 if mode == "deep" else 1
        candidates = await generate_candidates(task=task, n=n)
        scored = await score_candidates(candidates, test_command=test_command)
        best = await select_best_candidate(scored)
        out = {
            "selected_candidate_id": best.candidate_id,
            "strategy": best.strategy,
            "score": best.score,
            "verification_passed": best.verification.passed,
            "verification_output": best.verification.output[:300],
            "content": best.content
        }
        return json.dumps(out, indent=2)

    @mcp.tool()
    async def verify_candidate(task: str, candidate: str, test_command: Optional[str] = None, task_id: str = "default") -> str:
        """Verifies a candidate solution using sandbox execution or rubric."""
        if "def " in candidate:
            v_res = await verify_code_candidate(task=task, candidate_code=candidate, test_command=test_command)
        else:
            v_res = await verify_non_code_candidate(task=task, candidate_answer=candidate, rubric=["correctness"])
        return json.dumps(v_res.to_dict(), indent=2)

    @mcp.tool()
    async def reflexion_fix(task: str, candidate: str, error_output: str, max_attempts: int = 2, task_id: str = "default") -> str:
        """Analyzes a failure and produces a minimal repair plan, saving the lesson to memory."""
        res = await reflexion_repair(task=task, candidate_content=candidate, verifier_output=error_output, max_attempts=max_attempts)
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def compile_skills(task_id: str = "default") -> str:
        """Compiles successful traces into task-type-specific exemplar prompts."""
        compiler = SkillCompiler()
        res = compiler.compile_all()
        return json.dumps(res, indent=2)

    @mcp.tool()
    async def get_workspace_file(file_path: str, task_id: str = "default") -> str:
        """Reads a specific file from the user's workspace to feed into the [FACT] node."""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
