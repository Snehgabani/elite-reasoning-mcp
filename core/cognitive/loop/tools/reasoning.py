"""Reasoning Tool — Primary pipeline entry point (v2).

Runs the research-backed iterative reasoning pipeline with:
- Self-consistency path scoring (3 paths, scored and ranked)
- Iterative refinement loop (up to 3 rounds)
- Quality-gated feedback (retry if below threshold)
- Conditional routing (direct/standard/amplified)
"""

from __future__ import annotations

import json
import urllib.request
from typing import Annotated, Any, Literal

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from core.cognitive.loop.core.store import SingularityStore
from core.cognitive.loop.frameworks.abstention import calibrated_abstention
from core.cognitive.loop.frameworks.adaptive_consistency import faithfulness_score, run_adaptive_consensus
from core.cognitive.loop.frameworks.calibration_accumulator import accumulate_calibration
from core.cognitive.loop.frameworks.step_verifier import verify_steps
from core.cognitive.loop.pipeline.complete_pipeline import (
    CompletePipeline as ReasoningPipelineV2,  # v10 complete pipeline
)

_RUN_ANNOTATIONS = ToolAnnotations(
    title="Run reasoning pipeline",
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)

_INFO_ANNOTATIONS = ToolAnnotations(
    title="View pipeline configuration",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


class ReasoningResult(BaseModel):
    session_id: str
    mode: str
    route: str
    route_reason: str
    intent: str
    complexity: int
    techniques_applied: list[str]
    subproblems: list[dict[str, Any]]
    candidate_paths: list[dict[str, Any]]
    best_path_score: float
    refinement_rounds: int
    critique_results: list[dict[str, Any]]
    adversarial_challenges: list[dict[str, Any]]
    verification_gates: list[dict[str, Any]]
    verification_passed: bool
    abstained: bool = False
    abstention_reason: str = ""
    confidence: float
    quality_score: dict[str, Any]
    rubric_score: dict[str, Any]
    bias_scan: dict[str, Any]
    answer: str = ""
    synthesis_model: str = ""
    synthesis_duration_ms: int = 0
    pipeline_duration_ms: int
    warnings: list[str]


class PipelineInfo(BaseModel):
    mode: str
    version: str
    nodes: list[str]
    techniques: list[dict[str, Any]]
    total_techniques: int
    features: list[str]


_LLM_PROXY_URL = "http://127.0.0.1:4096/v1/chat/completions"
_LLM_MODEL = "gpt-oss:20b"


def _synthesize_answer(prompt: str, result) -> tuple[str, str]:
    """Execute the pipeline-generated reasoning structure through the local LLM
    proxy (research-backed: structured scaffolding + LLM execution outperforms
    plain prompting — STROT arXiv:2505.01636; 'Better Prompts, Better
    Usefulness' 2026; CoT Wei et al. 2022 lineage in TECHNIQUES registry).
    Returns (answer, model). Empty answer + empty model = LLM unavailable —
    caller falls back to scaffolding-only output with a warning."""
    try:
        template = getattr(result, "reasoning_template", "") or ""
        if not template:
            subs = "; ".join(
                s.get("name", "") for s in (getattr(result, "subproblems", None) or [])
            ) or "none"
            template = f"Framework: {result.selected_framework}. Subproblems: {subs}."
        llm_prompt = (
            "You are a reasoning executor. A structured reasoning pipeline "
            "produced the analysis structure below for the task. Execute the "
            "reasoning end-to-end and deliver a complete, concrete, final "
            "answer. Do not describe the structure — produce the answer.\n\n"
            f"TASK: {prompt}\n\nREASONING STRUCTURE:\n{template}\n\nFINAL ANSWER:"
        )
        body = json.dumps({
            "model": _LLM_MODEL,
            "messages": [{"role": "user", "content": llm_prompt}],
            "max_tokens": 1024,
            "temperature": 0.3,
        }).encode()
        req = urllib.request.Request(
            _LLM_PROXY_URL, data=body, headers={"Content-Type": "application/json"}
        )
        # Self-diagnosis fix (2026-08-12): one retry on transient failure —
        # local proxy is the synthesis single point of failure.
        last_err: Exception | None = None
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode())
                msg = data["choices"][0]["message"]
                answer = (msg.get("content") or "").strip()
                if not answer:
                    # gpt-oss:20b is a reasoning model: content can be empty while the
                    # reasoning field carries the actual output.
                    answer = (msg.get("reasoning") or "").strip()
                if answer:
                    return answer, _LLM_MODEL
                last_err = RuntimeError("empty completion")
            except Exception as e:  # noqa: BLE001 — any failure → retry once
                last_err = e
        if last_err is not None:
            raise last_err
        return "", ""
    except Exception:
        return "", ""


def register(mcp, store: SingularityStore):
    """Register reasoning tools."""

    @mcp.tool(name="reasoning_run", annotations=_RUN_ANNOTATIONS)
    def reasoning_run(
        prompt: Annotated[str, Field(min_length=1, max_length=16000)],
        mode: Literal["direct", "standard", "amplified"] = "amplified",
        synthesize: Annotated[bool, Field(default=True)] = True,
        search: Annotated[bool, Field(default=False)] = False,
    ) -> ReasoningResult:
        """Run research-backed iterative reasoning pipeline. Features: self-consistency (3 scored paths), iterative refinement (up to 3 rounds), quality-gated feedback, conditional routing. Modes: direct (A/B baseline), standard (fast), amplified (full). synthesize=True executes the generated reasoning structure through the local LLM proxy and returns a real answer (falls back to structure-only with a warning if the proxy is unavailable). search=True enables v15 LATS-style bounded tree search over alternative reasonings (arXiv:2310.04406) instead of flat consensus sampling. Use FIRST for non-trivial tasks. Skip for trivial acknowledgements.

        Techniques: Self-Consistency (+17.9%), Self-Refine (+5-40%),
        Tree of Thoughts (4%→74%), Least-to-Most, Step-Back, System 2 Attention.
        """
        pipeline = ReasoningPipelineV2(store, mode=mode)
        result = pipeline.run(prompt, mode=mode)

        # BUGFIX: quality score was computed but never written to the scorecard
        # table — diagnostics quality trend stayed no_data forever. Record it now.
        store.record_quality_score(
            result.quality_score, "task_success", notes=f"reasoning_run:{result.session_id}"
        )

        # UPGRADE: execute the generated reasoning structure through the local
        # LLM proxy so the tool returns an actual answer, not just scaffolding.
        # Instrumented (2026-08-12, self-diagnosis round): synthesis wall-time is
        # recorded so tool_usage/telemetry no longer hides the real latency.
        answer, synthesis_model = "", ""
        synthesis_duration_ms = 0
        warnings = list(result.warnings)
        verification = None
        if synthesize:
            template = getattr(result, "reasoning_template", "") or ""
            if not template:
                subs = "; ".join(
                    s.get("name", "") for s in (getattr(result, "subproblems", None) or [])
                ) or "none"
                template = f"Framework: {result.selected_framework}. Subproblems: {subs}."
            # v15 P0 #1: RASC-style adaptive self-consistency (arXiv:2408.17017).
            # Samples up to 5 temperature-jittered executions of the reasoning
            # structure, early-stops when a stable majority emerges, and
            # faithfulness-weights the vote (down-weights planning meta-talk).
            #
            # v15 P0 #5 (search=True): LATS-style bounded tree search
            # (arXiv:2310.04406) replaces flat sampling — UCB-guided expansion
            # over alternative reasonings, faithfulness-scored, best branch
            # executed. Fail-open: falls back to flat consensus on expand error.
            if search:
                from core.cognitive.loop.frameworks.lats_search import lats_search

                def _lats_expand(parent_summary: str, depth: int) -> list[str]:
                    try:
                        branch_prompt = (
                            f"Task: {prompt}\n\n"
                            f"Reasoning template: {template}\n\n"
                            f"Already explored: {parent_summary or 'root'}\n\n"
                            "Produce ONE alternative, complete reasoning line for "
                            f"the task (branch {depth + 1}). Be concrete, not meta."
                        )
                        out, _ = _synthesize_answer(branch_prompt, result)
                        return [out] if out else []
                    except Exception:  # noqa: BLE001 — fail-open
                        return []

                lats = lats_search(
                    prompt,
                    expand_fn=_lats_expand,
                    score_fn=faithfulness_score,
                    max_nodes=5,
                    max_depth=2,
                    branch_factor=2,
                )
                answer = lats["best_summary"] or ""
                warnings.append(
                    f"LATS tree search: {lats['nodes_explored']} nodes, depth "
                    f"{lats['max_depth_reached']}, best score {lats['best_score']:.2f}."
                )
                if lats["warnings"]:
                    warnings.extend(f"LATS: {w}" for w in lats["warnings"])
                consensus = {
                    "samples_used": 1,  # 1 = suppress the consensus warning in
                    # search mode; LATS warning already reports node count.
                    "agreement": lats["best_score"],
                    "stopped_early": False,
                    "faithfulness_mean": lats["best_score"],
                    "answer": answer,
                    "model": _LLM_MODEL,
                    "duration_ms": lats["search_duration_ms"],
                }
                store.record_metric(
                    "lats_nodes", float(lats["nodes_explored"]), "nodes"
                )
            else:
                consensus = run_adaptive_consensus(prompt, template)
            answer, synthesis_model = consensus["answer"], consensus["model"]
            synthesis_duration_ms = consensus.get("duration_ms", 0)
            if consensus.get("samples_used", 0) > 1:
                warnings.append(
                    f"Adaptive self-consistency: {consensus['samples_used']} samples, "
                    f"agreement {consensus['agreement']:.0%}, "
                    f"early-stop {consensus['stopped_early']}."
                )
            if not answer:
                warnings.append(
                    "LLM synthesis unavailable (proxy 127.0.0.1:4096 returned no answer); "
                    "returned reasoning structure only."
                )
            else:
                store.record_metric(
                    "reasoning_synthesis_ms", float(synthesis_duration_ms), "ms"
                )
                # v15 telemetry: consensus quality signals for longitudinal tracking.
                store.record_metric(
                    "consensus_samples", float(consensus["samples_used"]), "samples"
                )
                store.record_metric(
                    "consensus_agreement", float(consensus["agreement"]), "frac"
                )
                store.record_metric(
                    "consensus_faithfulness_mean",
                    float(consensus["faithfulness_mean"]),
                    "frac",
                )

            # v15 P0 #2: PRM-style generative step verification (GenPRM
            # arXiv:2504.00891, DeepSeek-GRM arXiv:2504.02495). Runs only when
            # an answer was synthesized; fail-open (verified=None) on LLM down.
            verification = None
            if answer and mode != "direct":
                verification = verify_steps(
                    prompt,
                    answer,
                    subproblems=result.subproblems,
                    max_steps=3,
                    pass_threshold=0.7,
                )
                if verification["verification_score"] is not None:
                    store.record_metric(
                        "verification_score",
                        float(verification["verification_score"]),
                        "frac",
                    )
                    warnings.append(
                        f"Step verification: {'PASS' if verification['verified'] else 'FAIL'} "
                        f"({verification['verification_score']:.2f}, "
                        f"{len(verification['steps'])} steps, "
                        f"{verification['duration_ms']}ms)."
                    )
                else:
                    warnings.append(
                        "Step verification unavailable (LLM down) — answer unverified."
                    )

        # Quality gate: pipeline quality AND (step verification, when available).
        verification_passed = result.quality_passed
        if verification is not None and verification["verified"] is not None:
            verification_passed = bool(
                result.quality_passed and verification["verified"]
            )

        # v15 P1: calibration auto-accumulator — every answered run auto-logs
        # one resolved calibration datapoint (confidence vs gate-pass outcome)
        # so n grows without manual predict/resolve steps. Fail-safe inside.
        if answer:
            auto_cal = accumulate_calibration(
                store,
                prompt,
                confidence=result.framework_confidence,
                correct=verification_passed,
            )
            if auto_cal.get("total_predictions"):
                store.record_metric(
                    "calibration_n",
                    float(auto_cal["total_predictions"]),
                    "count",
                )

        # v15 P0 #3: calibrated abstention (TACL 2025 abstention survey;
        # AbstentionBench — reasoning models over-answer ~24%). Post-hoc
        # selective-prediction gate: flag low-confidence output loudly instead
        # of serving it as confirmed. Fail-open: no decision when unverified.
        abstained = False
        abstention_reason = ""
        if answer:
            abstention = calibrated_abstention(
                verification_score=(
                    verification["verification_score"]
                    if verification is not None else None
                ),
                consensus_agreement=consensus.get("agreement", 0.0),
                confidence=result.framework_confidence,
                quality_score=result.quality_score,
                mode=mode,
            )
            abstained = bool(abstention["abstained"])
            abstention_reason = abstention["reason"]
            if abstained:
                warnings.append(f"ABSTAINED: {abstention_reason}")
                store.record_metric("abstention_flag", 1.0, "count")

        return ReasoningResult(
            session_id=result.session_id,
            mode=mode,
            route=mode,
            route_reason=(f"Smart framework selection: {result.selected_framework} "
                          f"(confidence {result.framework_confidence:.2f})"),
            intent=result.intent,
            complexity=result.complexity,
            techniques_applied=result.techniques_applied,
            subproblems=[
                {"index": sp.get("index", i), "name": sp.get("name", ""),
                 "description": sp.get("description", ""),
                 "validation": sp.get("validation", ""),
                 "anti_patterns": sp.get("anti_patterns", []),
                 "solution_guidance": sp.get("solution_guidance", "")}
                for i, sp in enumerate(result.subproblems)
            ],
            candidate_paths=[],
            best_path_score=0.0,
            refinement_rounds=result.retry_count,
            critique_results=[
                {"dimension": c.get("dimension", ""), "question": c.get("question", ""),
                 "resolution": c.get("resolution", "")}
                for c in result.critique_dimensions
            ],
            adversarial_challenges=result.adversarial_challenges,
            verification_gates=[],
            verification_passed=verification_passed,
            abstained=abstained,
            abstention_reason=abstention_reason,
            confidence=result.framework_confidence,
            quality_score={"total_score": result.quality_score,
                           "adherence": result.adherence_score,
                           "readability": result.readability_score},
            rubric_score={},
            bias_scan={"flags": result.bias_flags},
            answer=answer,
            synthesis_model=synthesis_model,
            synthesis_duration_ms=synthesis_duration_ms,
            pipeline_duration_ms=result.duration_ms,
            warnings=warnings,
        )

    @mcp.tool(name="reasoning_info", annotations=_INFO_ANNOTATIONS)
    def reasoning_info(
        mode: Literal["direct", "standard", "amplified"] = "amplified",
    ) -> PipelineInfo:
        """View pipeline v2 configuration, features, active techniques with research citations. Use to understand what the pipeline does. Read-only.

        v2 features: iterative refinement, self-consistency scoring, conditional routing.
        """
        pipeline = ReasoningPipelineV2(store, mode=mode)
        info = pipeline.get_pipeline_info()

        return PipelineInfo(
            mode=info["mode"],
            version=info["version"],
            nodes=info["nodes"],
            techniques=info["techniques"],
            total_techniques=info["total_techniques"],
            features=info["features"],
        )
