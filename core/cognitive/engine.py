"""
Elite Cognitive Engine: The Supreme Unified Cognitive Architecture.
Fuses Loop MCP (Meta-Cognitive Routing, Calibration, Bias Scan, Benchmarking)
with Elite Singularity MCP (Closed-Loop StateGraph, AST Gating, Cryptographic Diffs).
Includes Real-Time Task Tracker & Watchdog Telemetry.
"""

import asyncio
import json
import os
import time
from typing import Any, Dict, Optional

from core.cognitive.agent import build_reasoning_graph
from core.cognitive.leverage.enforcer import GatedEnforcer
from core.cognitive.leverage.lessons import LessonStore
from core.cognitive.leverage.logic_verifier import LogicVerifier
from core.cognitive.leverage.prm_verifier import ProcessRewardModel
from core.cognitive.leverage.self_discover import compose_reasoning_topology as _compose_topology
from core.cognitive.leverage.task_watcher import TaskTracker

# Loop imports
from core.cognitive.loop.core.classifier import classify_prompt
from core.cognitive.loop.core.store import SingularityStore
from core.cognitive.loop.pipeline.bias_scanner import run_bias_scan


class EliteCognitiveEngine:
    """The unified cognitive loop & execution engine."""

    def __init__(self, brain_dir: Optional[str] = None):
        self.brain_dir = brain_dir or os.environ.get("ELITE_BRAIN_DIR", os.path.expanduser("~/.elite-reasoning/brain"))
        os.makedirs(self.brain_dir, exist_ok=True)
        self.prm = ProcessRewardModel()
        self.lessons = LessonStore(os.path.join(self.brain_dir, "lessons.jsonl"))
        self.logic = LogicVerifier()
        self.enforcer = GatedEnforcer(self.brain_dir)
        self.store = SingularityStore(self.brain_dir)
        self._graph_app = None

    def get_graph_app(self):
        if self._graph_app is None:
            try:
                self._graph_app = build_reasoning_graph()
            except Exception:
                self._graph_app = None
        return self._graph_app

    async def execute_mix(
        self,
        task: str,
        task_id: Optional[str] = None,
        task_type: str = "hard_problem",
        max_iterations: int = 3,
        enable_prm: bool = True,
        enable_bias_scan: bool = True,
    ) -> Dict[str, Any]:
        """Return a checkable task contract. This does not generate the user's answer."""
        start_time = time.perf_counter()
        task_id = task_id or f"mix-{int(time.time() * 1000)}"

        # Telemetry: Register task start
        TaskTracker.start_task(task_id, task, node="meta_routing")

        # Phase 1: Loop Meta-Cognitive Routing
        classification = classify_prompt(task)
        complexity = classification.complexity
        intent = classification.intent
        route_mode = classification.thinking_mode
        TaskTracker.heartbeat(task_id, node="bias_scan", progress_pct=25)

        # Phase 2: Loop Bias Scan
        bias_report = {}
        if enable_bias_scan:
            try:
                res = run_bias_scan(task)
                flags = []
                for rf in res.red_flags:
                    if hasattr(rf, "__dict__"):
                        flags.append(vars(rf))
                    elif isinstance(rf, dict):
                        flags.append(rf)
                    else:
                        flags.append(str(rf))
                bias_report = {
                    "red_flags": flags,
                    "sycophancy_score": res.sycophancy_score,
                    "confidence_evidence_gap": res.confidence_evidence_gap,
                    "overall_risk": res.overall_risk,
                    "recommendations": res.recommendations,
                }
            except Exception as e:
                bias_report = {"warning": f"Bias scan fallback: {e}"}

        # Phase 3: Singularity Relevant Lessons
        relevant_lessons = self.lessons.search_relevant(task, n=5)

        # Phase 4 & 6: Self-Discover Dynamic Topology & Logic Verification in Parallel
        TaskTracker.heartbeat(task_id, node="self_discover_topology", progress_pct=50)
        topology_res, logic_check = await asyncio.gather(
            _compose_topology(task), self.logic.verify_argument(task), return_exceptions=False
        )

        if isinstance(topology_res, str):
            try:
                topology = json.loads(topology_res)
            except Exception:
                topology = {"selected_atomic_modules": ["Decompose problem", "Critical Thinking"]}
        else:
            topology = topology_res or {}

        # Phase 5: Fast PRM Invariant Check on Hypothesis
        TaskTracker.heartbeat(task_id, node="prm_invariant_gate", progress_pct=75)
        prm_check = self.prm.verify_step_sync(f"Hypothesis formulation for: {task}")
        prm_passed = prm_check.get("passed", True)
        prm_score = prm_check.get("prm_score", 0.95)

        logic_valid = logic_check.get("valid", True)

        duration_ms = (time.perf_counter() - start_time) * 1000
        selected_mods = topology.get("selected_atomic_modules") or topology.get("selected_modules") or []

        from core.reasoning.task_contract import compile_task_contract
        from core.cognitive.trajectory_guardian import GLOBAL_TRAJECTORY_GUARDIAN

        contract = compile_task_contract(task, int(complexity) if isinstance(complexity, int) else 0)
        gate_token = GLOBAL_TRAJECTORY_GUARDIAN.record_pre_edit_contract(task_id, task)
        recency_envelope = GLOBAL_TRAJECTORY_GUARDIAN.build_recency_directive(task_id)

        quality_score = 1.0 if (prm_passed and logic_valid) else 0.5
        mandatory_chaining_directive = (
            "🚨 MANDATORY STEP-LOCKED LIFECYCLE DIRECTIVE (DO NOT BYPASS):\n"
            f"1. Checkpoint 1 [PRE-EDIT]  : Active constraints compiled. Gate token: {gate_token.token}\n"
            "2. Checkpoint 2 [DURING-EDIT]: After modifying any file/code, you MUST call `elite_verify(check='syntax', code=...)` and `elite_verify(check='cegis', code=...)`.\n"
            "3. Checkpoint 3 [POST-EDIT]  : You MUST call `elite_verify(check='tests', command='pytest ...')` before replying.\n"
            "4. HARD INVARIANT: You are strictly forbidden from delivering final text to the user without a passing `elite_verify` receipt."
        )

        result = {
            "task_id": task_id,
            "task_type": task_type,
            "status": "SUCCESS",
            "scaffold_status": "scaffolded",
            "gate_token": gate_token.token,
            "mandatory_chaining_directive": mandatory_chaining_directive,
            "recency_step_lock": recency_envelope,
            "note": "This legacy path records checkpoint state and compiles a task contract. The host must report edits/checks; verify evidence with elite_verify.",
            "complexity": complexity,
            "intent": intent,
            "route": route_mode,
            "bias_scan": bias_report,
            "injected_lessons_count": len(relevant_lessons),
            "topology_modules": selected_mods,
            "prm_initial_score": prm_score,
            "prm_passed": prm_passed,
            "logic_valid": logic_valid,
            "quality_score": quality_score,
            "duration_ms": round(duration_ms, 2),
            "task_contract": contract.to_dict(),
            "next_action": contract.next_action,
        }

        TaskTracker.finish_task(
            task_id=task_id,
            status="SUCCESS",
            result_summary=f"Contract next_action={contract.next_action}; latency={duration_ms:.1f}ms",
            quality_score=quality_score,
        )
        return result


# Global Singleton
_COGNITIVE_ENGINE = EliteCognitiveEngine()
_MIX_ENGINE = _COGNITIVE_ENGINE

__all__ = ["EliteCognitiveEngine", "_COGNITIVE_ENGINE", "_MIX_ENGINE"]
