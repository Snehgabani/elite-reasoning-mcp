"""Reasoning Decomposition Tool — Break down complex tasks into
structured, evidence-gated steps.

This is the primary entry point for reasoning enhancement. It:
1. Classifies the prompt (intent, complexity, risk)
2. Generates a structured execution plan with evidence gates
3. Surfaces relevant anti-patterns from memory
4. Recommends the smallest sufficient reasoning chain

Research basis: Chain-of-Thought (Wei et al., 2022), Tree of Thoughts
(Yao et al., 2023), Self-Consistency (Wang et al., 2023).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict
from typing import Annotated, Any

from pydantic import BaseModel, Field

from core.cognitive.loop.core.classifier import classify_prompt
from core.cognitive.loop.core.store import SingularityStore


class DecomposeInput(BaseModel):
    prompt: Annotated[str, Field(min_length=1, max_length=16000, description="The task or question to decompose")]
    include_memory: Annotated[
        bool, Field(default=True, description="Surface relevant past decisions and anti-patterns")
    ]
    depth: Annotated[str, Field(default="auto", description="Decomposition depth: auto, shallow, standard, deep")]


class StepPlan(BaseModel):
    index: int
    name: str
    action: str
    evidence_required: str
    validation_gate: str
    estimated_complexity: int


class DecomposeResult(BaseModel):
    session_id: str
    intent: str
    complexity: int
    budget_tier: str
    thinking_mode: str
    zoom_level: str
    risk_signals: list[str]
    recommended_tools: list[str]
    steps: list[StepPlan]
    anti_patterns: list[dict[str, Any]]
    memory_context: list[dict[str, Any]]
    confidence: float
    warnings: list[str] = Field(default_factory=list)


def register(mcp, store: SingularityStore):
    """Register the reasoning_decompose tool on the MCP server."""

    @mcp.tool(name="reasoning_decompose")
    def reasoning_decompose(
        prompt: Annotated[str, Field(min_length=1, max_length=16000)],
        include_memory: bool = True,
        depth: str = "auto",
    ) -> DecomposeResult:
        """Decompose a complex task into structured, evidence-gated execution steps.

        Classifies your prompt (intent, complexity, risk), generates a step-by-step
        plan with validation gates, surfaces relevant past mistakes, and recommends
        the smallest sufficient reasoning chain.

        Use this FIRST for any non-trivial task. It tells you exactly what to do,
        what evidence to collect, and what to watch out for.
        """
        start = time.time()
        classification = classify_prompt(prompt)
        session_id = f"rs_{uuid.uuid4().hex[:12]}"

        # Determine actual depth
        if depth == "auto":
            depth = (
                "shallow"
                if classification.complexity <= 2
                else "standard"
                if classification.complexity <= 4
                else "deep"
            )

        # Generate execution plan
        steps = _generate_steps(prompt, classification, depth)

        # Surface anti-patterns
        anti_patterns = []
        if include_memory:
            anti_patterns = store.check_anti_patterns(prompt, limit=5)

        # Surface memory context
        memory_context = []
        if include_memory:
            memory_context = store.search_memory(prompt, limit=5, min_trust=0.5)

        # Compute confidence estimate
        confidence = _estimate_confidence(classification, anti_patterns, memory_context)

        # Warnings
        warnings = []
        if classification.risk_signals:
            warnings.append(
                f"Risk signals detected: {', '.join(classification.risk_signals)}. Use reasoning_verify before completion."
            )
        if anti_patterns:
            warnings.append(f"{len(anti_patterns)} relevant past mistake(s) found. Review before proceeding.")
        if classification.complexity >= 4 and not classification.recommended_tools:
            warnings.append("High complexity but no reasoning tools recommended — consider using reasoning_amplify.")

        # Persist session
        steps_data = [asdict(s) for s in steps]
        store.create_session(
            session_id=session_id,
            prompt=prompt[:2000],
            intent=classification.intent,
            complexity=classification.complexity,
            budget_tier=classification.budget_tier,
            steps=steps_data,
        )

        # Log metrics
        duration_ms = int((time.time() - start) * 1000)
        store.log_tool_usage(
            "reasoning_decompose", prompt[:200], json.dumps({"steps": len(steps)}), session_id, duration_ms
        )
        store.record_metric("decompose_duration_ms", duration_ms, "ms")
        store.record_metric("decompose_complexity", classification.complexity)

        return DecomposeResult(
            session_id=session_id,
            intent=classification.intent,
            complexity=classification.complexity,
            budget_tier=classification.budget_tier,
            thinking_mode=classification.thinking_mode,
            zoom_level=classification.zoom_level,
            risk_signals=classification.risk_signals,
            recommended_tools=classification.recommended_tools,
            steps=steps,
            anti_patterns=anti_patterns,
            memory_context=[
                {"id": m["id"], "type": m["memory_type"], "content": m["content"][:300], "trust": m["trust_score"]}
                for m in memory_context
            ],
            confidence=confidence,
            warnings=warnings,
        )


def _generate_steps(prompt: str, cls, depth: str) -> list[StepPlan]:
    """Generate structured execution steps based on classification."""
    steps = []
    idx = 1

    # Step 1: Preflight (always)
    steps.append(
        StepPlan(
            index=idx,
            name="preflight",
            action=f"Confirm task scope: intent={cls.intent}, complexity={cls.complexity}/5, "
            f"budget={cls.budget_tier}, mode={cls.thinking_mode}, zoom={cls.zoom_level}. "
            f"Review {len(cls.risk_signals)} risk signal(s).",
            evidence_required="Task scope confirmed, risks acknowledged.",
            validation_gate="No unresolved risk signals.",
            estimated_complexity=1,
        )
    )
    idx += 1

    # Step 2: Memory check (if memory available)
    steps.append(
        StepPlan(
            index=idx,
            name="memory_check",
            action="Search past decisions and anti-patterns for relevant context. "
            "Apply trusted memory items; quarantine low-trust or sensitive items.",
            evidence_required="Relevant past decisions reviewed. Anti-patterns acknowledged.",
            validation_gate="No unaddressed anti-patterns from past sessions.",
            estimated_complexity=1,
        )
    )
    idx += 1

    # Step 3-N: Core execution steps (varies by depth and intent)
    if cls.intent == "debug":
        steps.extend(_debug_steps(idx, prompt))
        idx += 3
    elif cls.intent == "build":
        steps.extend(_build_steps(idx, prompt, cls.complexity))
        idx += 3 if cls.complexity >= 3 else 2
    elif cls.intent in ("decide", "design"):
        steps.extend(_decision_steps(idx, prompt))
        idx += 3
    elif cls.intent == "research":
        steps.extend(_research_steps(idx, prompt))
        idx += 3
    elif cls.intent == "deploy":
        steps.extend(_deploy_steps(idx, prompt))
        idx += 3
    elif cls.intent == "audit":
        steps.extend(_audit_steps(idx, prompt))
        idx += 3
    else:
        steps.extend(_general_steps(idx, prompt, cls.complexity))
        idx += 2 if cls.complexity >= 3 else 1

    # Validation step
    steps.append(
        StepPlan(
            index=idx,
            name="validate",
            action="Run all validation gates. Verify evidence requirements are met. "
            "If any gate fails, return to the failing step and fix.",
            evidence_required="All validation gates passed. Evidence attached.",
            validation_gate="All previous steps have passed status with evidence.",
            estimated_complexity=2,
        )
    )
    idx += 1

    # Calibration step (for high complexity)
    if cls.complexity >= 3:
        steps.append(
            StepPlan(
                index=idx,
                name="calibrate",
                action="Assess confidence in the outcome. Log calibration prediction if making "
                "a claim about correctness, performance, or suitability.",
                evidence_required="Confidence score with justification. Calibration prediction logged.",
                validation_gate="Confidence >= 0.70 or explicit uncertainty documented.",
                estimated_complexity=1,
            )
        )
        idx += 1

    # Learning step (always last)
    steps.append(
        StepPlan(
            index=idx,
            name="learn",
            action="Record key decisions, any mistakes found, and high-value context for "
            "future sessions. Update quality score if outcome is measurable.",
            evidence_required="Decision rationale recorded. Mistakes (if any) logged with root cause.",
            validation_gate="At least one learning artifact persisted.",
            estimated_complexity=1,
        )
    )

    return steps


def _debug_steps(idx: int, prompt: str) -> list[StepPlan]:
    return [
        StepPlan(
            idx,
            "reproduce",
            "Reproduce the error. Capture exact error message, stack trace, and conditions.",
            "Error reproduced with exact output.",
            "Error message matches reported issue.",
            2,
        ),
        StepPlan(
            idx + 1,
            "root_cause",
            "Identify root cause using five-whys or binary search. Document the causal chain.",
            "Root cause identified with evidence chain.",
            "Root cause explains all observed symptoms.",
            3,
        ),
        StepPlan(
            idx + 2,
            "fix_verify",
            "Implement minimal fix. Run existing tests. Verify no regressions.",
            "Fix applied. All tests pass. No new warnings.",
            "Test suite green. Original error resolved.",
            2,
        ),
    ]


def _build_steps(idx: int, prompt: str, complexity: int) -> list[StepPlan]:
    steps = [
        StepPlan(
            idx,
            "design",
            "Define interface contract, data structures, and error handling strategy.",
            "Interface documented. Edge cases enumerated.",
            "No unhandled error paths.",
            2,
        ),
        StepPlan(
            idx + 1,
            "implement",
            "Implement focused changes. Keep each commit atomic and testable.",
            "Code written. Unit tests for new behavior.",
            "Lint clean. Tests pass.",
            3,
        ),
    ]
    if complexity >= 3:
        steps.append(
            StepPlan(
                idx + 2,
                "integration",
                "Verify integration with existing code. Run full test suite.",
                "Integration tests pass. No regressions.",
                "Full suite green.",
                2,
            )
        )
    return steps


def _decision_steps(idx: int, prompt: str) -> list[StepPlan]:
    return [
        StepPlan(
            idx,
            "enumerate_options",
            "List all viable options with their constraints and requirements.",
            "At least 2 options enumerated with pros/cons.",
            "No option dismissed without reason.",
            2,
        ),
        StepPlan(
            idx + 1,
            "adversarial_review",
            "Challenge each option from security, scalability, and maintenance perspectives.",
            "Each option challenged on 3+ axes. Weaknesses documented.",
            "No unaddressed critical weakness.",
            3,
        ),
        StepPlan(
            idx + 2,
            "decide_record",
            "Make decision with documented rationale. Record alternatives rejected and why.",
            "Decision recorded. Rationale documented. Alternatives preserved.",
            "Decision rationale is self-contained.",
            1,
        ),
    ]


def _research_steps(idx: int, prompt: str) -> list[StepPlan]:
    return [
        StepPlan(
            idx,
            "gather_evidence",
            "Collect relevant sources, benchmarks, and prior art. Verify recency.",
            "At least 3 sources cited. Recency verified.",
            "No source older than 2 years without justification.",
            2,
        ),
        StepPlan(
            idx + 1,
            "synthesize",
            "Synthesize findings into structured claims with confidence levels.",
            "Claims mapped to evidence. Confidence assigned.",
            "Every claim has at least one supporting source.",
            3,
        ),
        StepPlan(
            idx + 2,
            "verify_claims",
            "Cross-check claims for contradictions. Flag unsupported assertions.",
            "Contradictions resolved. Unsupported claims flagged.",
            "No contradictions remain.",
            2,
        ),
    ]


def _deploy_steps(idx: int, prompt: str) -> list[StepPlan]:
    return [
        StepPlan(
            idx,
            "pre_deploy_check",
            "Capture current state. Run smoke tests. Verify rollback plan exists.",
            "Before-state captured. Smoke tests pass. Rollback documented.",
            "Rollback procedure tested.",
            2,
        ),
        StepPlan(
            idx + 1,
            "deploy",
            "Execute deployment with monitoring. Watch for error rate spike.",
            "Deployment completed. Metrics within bounds.",
            "Error rate < baseline + 10%.",
            3,
        ),
        StepPlan(
            idx + 2,
            "post_deploy_verify",
            "Verify deployment. Run post-deploy smoke tests. Compare metrics.",
            "Post-deploy tests pass. Metrics nominal.",
            "All health checks green.",
            2,
        ),
    ]


def _audit_steps(idx: int, prompt: str) -> list[StepPlan]:
    return [
        StepPlan(
            idx,
            "scope_audit",
            "Define audit scope, boundaries, and success criteria.",
            "Scope documented. Criteria defined.",
            "Scope covers all risk areas.",
            1,
        ),
        StepPlan(
            idx + 1,
            "execute_audit",
            "Run audit checks systematically. Document findings with severity.",
            "All checks executed. Findings categorized.",
            "No finding without severity rating.",
            3,
        ),
        StepPlan(
            idx + 2,
            "report_remediate",
            "Generate findings report. Prioritize remediation. Create action items.",
            "Report generated. Actions prioritized.",
            "All P0/P1 findings have remediation plan.",
            2,
        ),
    ]


def _general_steps(idx: int, prompt: str, complexity: int) -> list[StepPlan]:
    steps = [
        StepPlan(
            idx,
            "execute",
            "Perform the task with focused execution. Document key decisions.",
            "Task completed. Key decisions noted.",
            "No unresolved blockers.",
            2,
        ),
    ]
    if complexity >= 3:
        steps.append(
            StepPlan(
                idx + 1,
                "review",
                "Review output for completeness, correctness, and edge cases.",
                "Output reviewed. Edge cases checked.",
                "No obvious issues remain.",
                2,
            )
        )
    return steps


def _estimate_confidence(cls, anti_patterns: list, memory_context: list) -> float:
    """Estimate initial confidence based on classification and available context."""
    base = 0.50
    # Complexity reduces confidence
    base -= (cls.complexity - 1) * 0.05
    # Risk signals reduce confidence
    base -= len(cls.risk_signals) * 0.05
    # Memory context increases confidence
    base += min(0.15, len(memory_context) * 0.03)
    # Anti-patterns increase awareness (slightly increase confidence in avoidance)
    base += min(0.10, len(anti_patterns) * 0.02)
    # Trivial tasks start high
    if cls.budget_tier == "trivial":
        base = 0.85
    return round(max(0.20, min(0.95, base)), 2)
