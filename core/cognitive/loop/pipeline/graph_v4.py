"""Pipeline v4 — Round 3 upgrades integrated.

Adds 5 new research-backed nodes to the v3 pipeline:
1. ReasoningPromptGenerator — Converts structure into guided reasoning prompt (CRITICAL)
2. PathEnsembleNode — Combines insights from all paths (HIGH)
3. ProgressiveComplexityNode — Start simple, escalate if needed (HIGH)
4. OutcomePredictorNode — Predict quality before generation (MEDIUM)
5. TaskAdaptiveTechniqueSelector — Choose techniques by task type (MEDIUM)

Key improvement: v4 generates a GUIDED REASONING PROMPT that tells the LLM
exactly HOW to use the pipeline structure, not just WHAT structure exists.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from core.cognitive.loop.core.store import SingularityStore
from core.cognitive.loop.pipeline.graph_v2 import (
    AdversarialVerifyNode,
    CalibrationNode,
    ClassifyAndRouteNode,
    DecomposeNode,
    QualityScoreNode,
    SelfConsistencyNode,
    SelfRefineCritiqueNode,
    SelfRefineResolutionNode,
    StepBackNode,
)
from core.cognitive.loop.pipeline.nodes_v3 import (
    AdversarialSelfPlayNode,
    MetaReasoningNode,
    OutputStructuringNode,
    SynthesisNode,
    VerificationNode,
)
from core.cognitive.loop.pipeline.nodes_v4 import (
    OutcomePredictorNode,
    PathEnsembleNode,
    PipelineStateV4,
    ProgressiveComplexityNode,
    ReasoningPromptGenerator,
    TaskAdaptiveTechniqueSelector,
)


class ReasoningPipelineV4:
    """v4 pipeline with Round 3 upgrades.

    Modes:
    - direct: Classify only (baseline for A/B)
    - standard: Classify → Decompose → SelfConsistency → Synthesis → Prompt → Score
    - amplified: Full pipeline with all v4 nodes + adaptive refinement

    Key improvement over v3: Generates GUIDED REASONING PROMPT
    """

    MODES = {
        "direct": ["classify_route"],
        "standard": [
            "classify_route",
            "decompose",
            "self_consistency",
            "synthesis",
            "reasoning_prompt_generator",
            "verification",
            "calibrate",
            "quality_score",
        ],
        "amplified": [
            "classify_route",
            "task_adaptive_selector",
            "meta_reasoning",
            "step_back",
            "decompose",
            "self_consistency",
            "path_ensemble",
            "self_refine_critique",
            "self_refine_resolve",
            "adversarial_verify",
            "adversarial_self_play",
            "synthesis",
            "output_structuring",
            "reasoning_prompt_generator",
            "outcome_predictor",
            "verification",
            "calibrate",
            "quality_score",
            "progressive_complexity",
        ],
    }

    NODE_REGISTRY = {
        # v2 nodes
        "classify_route": ClassifyAndRouteNode,
        "step_back": StepBackNode,
        "decompose": DecomposeNode,
        "self_consistency": lambda: SelfConsistencyNode(num_paths=3),
        "self_refine_critique": SelfRefineCritiqueNode,
        "self_refine_resolve": SelfRefineResolutionNode,
        "adversarial_verify": AdversarialVerifyNode,
        "calibrate": CalibrationNode,
        "quality_score": QualityScoreNode,
        # v3 nodes
        "meta_reasoning": MetaReasoningNode,
        "adversarial_self_play": AdversarialSelfPlayNode,
        "synthesis": SynthesisNode,
        "output_structuring": OutputStructuringNode,
        "verification": VerificationNode,
        # v4 nodes
        "reasoning_prompt_generator": ReasoningPromptGenerator,
        "path_ensemble": PathEnsembleNode,
        "progressive_complexity": ProgressiveComplexityNode,
        "outcome_predictor": OutcomePredictorNode,
        "task_adaptive_selector": TaskAdaptiveTechniqueSelector,
    }

    def __init__(self, store: SingularityStore, mode: str = "amplified"):
        self.store = store
        self.mode = mode

    def _build_nodes(self, mode: str) -> list:
        node_names = self.MODES.get(mode, self.MODES["standard"])
        nodes = []
        for name in node_names:
            factory = self.NODE_REGISTRY.get(name)
            if factory:
                if callable(factory) and not isinstance(factory, type):
                    nodes.append(factory())
                else:
                    nodes.append(factory())
        return nodes

    def run(self, prompt: str, mode: str | None = None) -> PipelineStateV4:
        """Execute the v4 pipeline with adaptive refinement."""
        start = time.time()
        session_id = f"rs_{uuid.uuid4().hex[:12]}"
        effective_mode = mode or self.mode

        # Initialize v4 state
        state = PipelineStateV4(
            prompt=prompt,
            session_id=session_id,
        )

        # Phase 1: Classify and route
        classify_node = ClassifyAndRouteNode()
        state = classify_node.execute(state, self.store)

        # Override mode based on route if not explicitly specified
        if mode is None:
            if state.route == "direct":
                effective_mode = "direct"
            elif state.route == "standard":
                effective_mode = "standard"
            else:
                effective_mode = "amplified"

        # Build node list
        nodes = self._build_nodes(effective_mode)

        # Phase 2: Execute pipeline nodes
        for node in nodes:
            if node.name == "classify_route":
                continue  # Already ran
            try:
                state = node.execute(state, self.store)
            except Exception as e:
                state.warnings.append(f"Node '{node.name}' failed: {str(e)[:200]}")

        # Phase 3: Adaptive refinement loop (amplified mode only)
        if effective_mode == "amplified":
            state = self._adaptive_refinement_loop(state)

        state.pipeline_duration_ms = int((time.time() - start) * 1000)

        # Record session
        try:
            self.store.create_session(
                session_id=session_id,
                prompt=prompt[:2000],
                intent=state.classification.intent if state.classification else "unknown",
                complexity=state.classification.complexity if state.classification else 0,
                budget_tier=state.classification.budget_tier if state.classification else "unknown",
                steps=[{"name": n.name, "duration_ms": state.node_durations.get(n.name, 0)} for n in nodes],
            )
            self.store.complete_session(
                session_id,
                outcome={
                    "quality_score": state.quality_score.get("total_score", 0),
                    "techniques": state.techniques_applied,
                    "route": effective_mode,
                    "refinement_rounds": state.refinement_round,
                    "early_stopped": state.early_stopped,
                    "predicted_quality": state.predicted_quality,
                    "escalation_triggered": state.escalation_triggered,
                },
                metrics={
                    "confidence": state.confidence,
                    "duration_ms": state.pipeline_duration_ms,
                    "path_scores": state.path_scores,
                    "counter_arguments": len(state.counter_arguments),
                    "verification_tests": len(state.verification_tests),
                    "reasoning_prompt_length": len(state.reasoning_prompt),
                },
                duration_ms=state.pipeline_duration_ms,
            )
            self.store.record_metric(
                "pipeline_v4_duration_ms", state.pipeline_duration_ms, "ms", {"mode": effective_mode}
            )
            self.store.record_metric("pipeline_v4_quality", state.quality_score.get("total_score", 0))
            self.store.record_metric("pipeline_v4_predicted_quality", state.predicted_quality)
        except Exception as exc:
            # Explicit non-fatal exception suppression
            _ = str(exc)

        return state

    def _adaptive_refinement_loop(self, state: PipelineStateV4) -> PipelineStateV4:
        """Adaptive refinement with early stopping."""
        refine_critique = SelfRefineCritiqueNode()
        refine_resolve = SelfRefineResolutionNode()
        quality_node = QualityScoreNode()
        calibrate_node = CalibrationNode()

        # Record initial quality
        initial_quality = state.quality_score.get("total_score", 0)
        state.refinement_quality_history.append(initial_quality)

        prev_quality = initial_quality

        for refine_round in range(state.max_refinement_rounds - 1):
            # Run refinement
            state = refine_critique.execute(state, self.store)
            state = refine_resolve.execute(state, self.store)
            state = calibrate_node.execute(state, self.store)
            state = quality_node.execute(state, self.store)

            current_quality = state.quality_score.get("total_score", 0)
            state.refinement_quality_history.append(current_quality)

            # Calculate improvement
            improvement = current_quality - prev_quality

            state.warnings.append(
                f"Refinement round {state.refinement_round + 1}: quality={current_quality:.3f} (Δ={improvement:+.3f})"
            )

            # Early stopping conditions
            if current_quality >= state.quality_threshold:
                state.warnings.append(f"Early stop: quality meets threshold ({state.quality_threshold})")
                state.early_stopped = True
                break

            if improvement < 0.05 and refine_round > 0:
                state.warnings.append(f"Early stop: diminishing returns (Δ={improvement:.3f} < 0.05)")
                state.early_stopped = True
                break

            if improvement < 0:
                state.warnings.append(f"Early stop: quality decreased (Δ={improvement:.3f})")
                state.early_stopped = True
                break

            prev_quality = current_quality

        return state

    def get_pipeline_info(self) -> dict[str, Any]:
        """Get pipeline configuration and technique details."""
        node_names = self.MODES.get(self.mode, [])
        return {
            "mode": self.mode,
            "version": "v4",
            "nodes": node_names,
            "total_nodes": len(node_names),
            "features": [
                "Guided reasoning prompt generator (converts structure to step-by-step instructions)",
                "Path ensemble voting (combines insights from all self-consistency paths)",
                "Progressive complexity (start simple, escalate if quality < threshold)",
                "Outcome prediction (estimate quality before LLM generates)",
                "Task-adaptive technique selection (choose techniques by task type)",
                "Adaptive refinement with early stopping (saves 30-50% compute)",
                "Synthesis node (combines outputs into structured answer)",
                "Adversarial self-play (devil's advocate counter-arguments)",
                "Verification gate (test cases and framework checks)",
                "Output structuring (section templates by intent)",
                "Meta-reasoning (technique selection rationale)",
                "Self-consistency with path scoring (3 paths, scored and ranked)",
                "Conditional routing (direct/standard/amplified)",
                "Memory cross-reference (anti-patterns injected per subproblem)",
                "Bias scanning (10 cognitive biases + sycophancy)",
            ],
        }
