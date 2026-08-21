"""
Micro-Step Cognitive Scaffolder for Small Language Models.
Executes multi-step reasoning workflows as decomposed atomic micro-steps
with state compaction and invariant boundary enforcement per step.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.cognitive.leverage.param_coercion import ParameterCoercionEngine
from core.cognitive.leverage.small_model_adapter import SmallModelAdapter


@dataclass
class MicroStepResult:
    step_index: int
    total_steps: int
    objective: str
    output: Dict[str, Any]
    duration_ms: float
    invariant_passed: bool
    violations: List[str] = field(default_factory=list)


@dataclass
class MicroScaffoldExecution:
    task: str
    completed_steps: List[MicroStepResult]
    is_success: bool
    final_payload: str
    total_duration_ms: float


class MicroStepScaffolder:
    """
    Manages bounded step-by-step execution for small models, enforcing invariant
    gates at every step transition to prevent error cascade.
    """

    def __init__(self, adapter: Optional[SmallModelAdapter] = None):
        self.adapter = adapter or SmallModelAdapter()
        self.coercion = ParameterCoercionEngine()

    def decompose_task(self, task: str, max_steps: int = 3) -> List[str]:
        """
        Deterministically decomposes a high-level task into concrete atomic sub-goals.
        """
        clean = task.strip()
        lines = [line.strip() for line in clean.splitlines() if line.strip()]
        numbered = [line for line in lines if line and line[0].isdigit() and ("." in line[:3] or ")" in line[:3])]
        if len(numbered) >= 2:
            return numbered[:max_steps]

        return [
            f"Analyze core requirements and state invariants for: {clean[:150]}",
            f"Execute concrete implementation/resolution for: {clean[:150]}",
            f"Verify correctness, edge cases, and constraint satisfaction for: {clean[:150]}",
        ][:max_steps]

    def execute_micro_step(
        self,
        task: str,
        step_index: int,
        total_steps: int,
        step_goal: str,
        generator_fn: Callable[[str], str],
        context_hints: Optional[List[str]] = None,
    ) -> MicroStepResult:
        """
        Runs a single micro-step using the provided generator function,
        repairs output deterministically, and validates invariants.
        """
        t0 = time.perf_counter()
        adapted = self.adapter.adapt_task(
            task=task,
            current_step=step_index,
            total_steps=total_steps,
            step_goal=step_goal,
            context_hints=context_hints,
        )

        raw_output = generator_fn(adapted.condensed_prompt)
        repaired = self.adapter.validate_and_repair_slm_output(raw_output)

        violations = []
        payload = str(repaired.get("payload", "")).strip()
        if not payload:
            violations.append("Empty step payload emitted")
        if "parse_error" in repaired and repaired["parse_error"] == "unparseable_output":
            violations.append("Output completely unparseable")

        duration_ms = (time.perf_counter() - t0) * 1000.0

        return MicroStepResult(
            step_index=step_index,
            total_steps=total_steps,
            objective=step_goal,
            output=repaired,
            duration_ms=round(duration_ms, 3),
            invariant_passed=len(violations) == 0,
            violations=violations,
        )

    def run_scaffolded_workflow(
        self,
        task: str,
        generator_fn: Callable[[str], str],
        max_steps: int = 3,
    ) -> MicroScaffoldExecution:
        """
        Runs the full chained micro-step workflow with intermediate invariant checking.
        """
        t0 = time.perf_counter()
        steps = self.decompose_task(task, max_steps=max_steps)
        total_steps = len(steps)
        completed: List[MicroStepResult] = []
        hints: List[str] = []

        all_ok = True
        for idx, step_goal in enumerate(steps, 1):
            res = self.execute_micro_step(
                task=task,
                step_index=idx,
                total_steps=total_steps,
                step_goal=step_goal,
                generator_fn=generator_fn,
                context_hints=hints,
            )
            completed.append(res)
            if not res.invariant_passed:
                all_ok = False
                break
            hints.append(f"Step {idx} payload: {str(res.output.get('payload', ''))[:100]}")

        total_ms = (time.perf_counter() - t0) * 1000.0
        final_payload = completed[-1].output.get("payload", "") if completed else ""

        return MicroScaffoldExecution(
            task=task,
            completed_steps=completed,
            is_success=all_ok,
            final_payload=str(final_payload),
            total_duration_ms=round(total_ms, 3),
        )
