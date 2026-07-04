"""Stateful workflow flight recorder for Elite Reasoning MCP.

This module converts a user request into a deterministic, evidence-gated
execution plan and persists it. It does not execute arbitrary actions itself;
it records the contract the agent must satisfy before claiming completion.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from core.eval.research_benchmarks import recommend_budget_tier
from core.orchestration.capabilities import build_capability_registry
from core.reasoning.nuclear_prompt import nuclear_prompt_breakdown, protocol_recommendation


def _utc_now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


def _classify_intent(prompt: str) -> str:
    lower = (prompt or "").lower()
    signals = {
        "debug": ("debug", "bug", "broken", "error", "traceback", "fix"),
        "build": ("build", "implement", "add", "create", "feature"),
        "audit": ("audit", "review", "verify", "health", "diagnose", "release"),
        "research": ("research", "evidence", "paper", "benchmark", "source", "citation"),
        "security": ("security", "auth", "secret", "credential", "prompt injection", "red team"),
        "memory": ("memory", "remember", "context", "personalization", "preference"),
        "deploy": ("deploy", "publish", "release", "ship", "production"),
    }
    scores = {
        intent: sum(1 for token in tokens if token in lower)
        for intent, tokens in signals.items()
    }
    intent, score = max(scores.items(), key=lambda item: item[1])
    return intent if score else "general"


def _complexity(prompt: str, intent: str) -> int:
    lower = (prompt or "").lower()
    score = 1
    if len(lower) > 600:
        score += 2
    elif len(lower) > 220:
        score += 1
    if intent in {"audit", "security", "deploy", "research"}:
        score += 2
    elif intent in {"build", "debug", "memory"}:
        score += 1
    if any(term in lower for term in ("production", "release", "security", "migration", "database", "end to end")):
        score += 1
    return max(1, min(5, score))


def _safe_store_call(default: Any, fn, *args, **kwargs) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception:
        return default


def _string_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value]


def _memory_context(store, prompt: str, limit: int) -> list[dict[str, Any]]:
    context: list[dict[str, Any]] = []

    for item in _safe_store_call([], store.search_memory_items, prompt, limit=limit):
        context.append(
            {
                "kind": "memory_item",
                "id": item.get("id"),
                "summary": item.get("content", "")[:300],
                "confidence": item.get("confidence"),
                "trust_score": item.get("trust_score"),
                "scope": item.get("scope"),
                "source": item.get("source"),
            }
        )

    for item in _safe_store_call([], store.check_anti_patterns, prompt, limit=3):
        context.append(
            {
                "kind": "anti_pattern",
                "id": item.get("id"),
                "summary": f"{item.get('mistake', '')} -> {item.get('fix', '')}"[:300],
                "severity": item.get("severity", "medium"),
            }
        )

    for item in _safe_store_call([], store.search_decisions, prompt, limit=3):
        context.append(
            {
                "kind": "decision",
                "id": item.get("id"),
                "summary": f"{item.get('decision', '')}: {item.get('rationale', '')}"[:300],
            }
        )

    return context[:limit]


def build_workflow_run(user_prompt: str, store=None, persist: bool = True) -> dict[str, Any]:
    """Build and optionally persist a workflow run contract."""
    cleaned = (user_prompt or "").strip()
    if not cleaned:
        raise ValueError("user_prompt is required")

    intent = _classify_intent(cleaned)
    complexity = _complexity(cleaned, intent)
    budget = recommend_budget_tier(cleaned, complexity)
    breakdown = nuclear_prompt_breakdown(cleaned)
    protocol = protocol_recommendation(cleaned, complexity)
    registry = build_capability_registry()
    memory_context = _memory_context(store, cleaned, limit=8) if store is not None else []
    run_id = f"wf_{uuid.uuid4().hex[:12]}"
    now = _utc_now()

    evidence_requirements = _string_list(breakdown.get("needed_evidence", []))
    validation_gates = _string_list(breakdown.get("validation_plan", []))
    required_checks = list(budget.required_checks)
    for check in required_checks:
        if check not in validation_gates:
            validation_gates.append(check)

    steps = [
        {
            "step_name": "preflight",
            "action": (
                "Confirm active IDE capabilities, applicable memory, task risk, and tool budget before execution."
            ),
            "status": "pending",
        },
        {
            "step_name": "plan",
            "action": (
                f"Use {protocol.get('primary_protocol', 'direct')} with budget tier {budget.tier}; "
                "state assumptions and select the smallest sufficient tool chain."
            ),
            "status": "pending",
        },
        {
            "step_name": "execute",
            "action": "Perform focused implementation/research/debug steps and capture material tool outputs as evidence.",
            "status": "pending",
        },
        {
            "step_name": "validate",
            "action": "Run the validation gates before claiming completion; record any blocker explicitly.",
            "status": "pending",
        },
        {
            "step_name": "calibrate",
            "action": "Assess confidence, note residual risks, and record calibration when making predictions.",
            "status": "pending",
        },
        {
            "step_name": "learn",
            "action": "Write back durable decisions, mistakes, and high-trust memory items after the outcome is known.",
            "status": "pending",
        },
    ]

    confidence = 0.55 + min(0.25, 0.04 * len(evidence_requirements)) + min(0.15, 0.03 * len(validation_gates))
    if memory_context:
        confidence += 0.05
    confidence = round(min(confidence, 0.95), 2)

    run = {
        "run_id": run_id,
        "user_prompt": cleaned,
        "intent": intent,
        "complexity": complexity,
        "budget_tier": budget.tier,
        "status": "planned",
        "confidence": confidence,
        "active_ide": registry.active_ide,
        "capability_warnings": list(registry.warnings),
        "recommendable_mcps": registry.names("mcp")[:20],
        "recommendable_skills": registry.names("skill")[:20],
        "protocol": protocol,
        "prompt_breakdown": breakdown,
        "evidence_requirements": evidence_requirements,
        "validation_gates": validation_gates,
        "memory_context": memory_context,
        "tool_budget": {
            "tier": budget.tier,
            "max_tool_calls": budget.max_tool_calls,
            "max_latency_ms": budget.max_latency_ms,
            "required_checks": required_checks,
            "escalation_condition": budget.escalation_condition,
        },
        "steps": steps,
        "created_at": now,
    }

    if persist and store is not None:
        store.record_workflow_run(run, steps)
    return run


def workflow_run_markdown(run: dict[str, Any]) -> str:
    """Render a workflow run as Markdown plus machine-readable JSON."""
    lines = [
        "# Elite Workflow Run",
        "",
        f"**Run ID:** `{run['run_id']}`",
        f"**Intent:** `{run['intent']}`",
        f"**Complexity:** {run['complexity']}/5",
        f"**Budget tier:** `{run['budget_tier']}`",
        f"**Confidence:** {run['confidence']:.0%}",
        f"**Active IDE:** `{run.get('active_ide', 'unknown')}`",
        "",
        "## Steps",
    ]
    for index, step in enumerate(run.get("steps", []), 1):
        lines.append(f"{index}. **{step['step_name']}**: {step['action']}")

    lines.extend(["", "## Evidence Requirements"])
    evidence = run.get("evidence_requirements", [])
    lines.extend(f"- {item}" for item in evidence) if evidence else lines.append("- No explicit evidence requirements detected.")

    lines.extend(["", "## Validation Gates"])
    gates = run.get("validation_gates", [])
    lines.extend(f"- {item}" for item in gates) if gates else lines.append("- State validation manually before completion.")

    memory_context = run.get("memory_context", [])
    lines.extend(["", "## Memory Context"])
    if memory_context:
        for item in memory_context:
            lines.append(f"- `{item.get('kind')}`: {item.get('summary')}")
    else:
        lines.append("- No trusted memory context matched this prompt.")

    warnings = run.get("capability_warnings", [])
    if warnings:
        lines.extend(["", "## Capability Warnings"])
        lines.extend(f"- {warning}" for warning in warnings)

    compact = {
        key: value
        for key, value in run.items()
        if key not in {"prompt_breakdown"}
    }
    lines.extend(["", "## JSON", "```json", json.dumps(compact, indent=2, sort_keys=True), "```"])
    return "\n".join(lines)


def workflow_status_markdown(run: dict[str, Any] | None) -> str:
    """Render a stored workflow run."""
    if not run:
        return "Workflow run not found."
    lines = [
        "# Elite Workflow Status",
        "",
        f"**Run ID:** `{run['run_id']}`",
        f"**Status:** `{run['status']}`",
        f"**Intent:** `{run['intent']}`",
        f"**Updated:** {run['updated_at']}",
        "",
        "## Steps",
    ]
    for step in run.get("steps", []):
        evidence = f" Evidence: {step['evidence']}" if step.get("evidence") else ""
        lines.append(f"- {step['step_index']}. `{step['status']}` {step['step_name']}: {step['action']}{evidence}")
    return "\n".join(lines)
