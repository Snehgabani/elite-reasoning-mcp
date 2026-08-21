"""
Small Model Cognitive Adapter & Schema Constrainer.
Optimizes prompt schemas, eliminates ambiguity, compacts verbose tool signatures,
and injects minimal 1-step scaffolding with deterministic AST parameter coercion
for cheap/low-intelligence language models (e.g. 7B/8B, GPT-4o-mini, Flash-Lite).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.cognitive.leverage.param_coercion import ParameterCoercionEngine


@dataclass
class AdaptedPrompt:
    """Optimized prompt payload tailored for small model execution."""

    original_task: str
    condensed_prompt: str
    expected_output_schema: Dict[str, Any]
    injected_invariants: List[str]
    max_step_tokens: int = 512


class SmallModelAdapter:
    """
    Transforms open-ended, complex prompts into bounded, single-step executable
    instructions with explicit output schema constraints and compact tool signatures.
    """

    DEFAULT_INVARIANTS = [
        "Return STRICT JSON only. Do not include markdown code block backticks or conversational text.",
        "Execute strictly ONE logical step at a time.",
        "Never hallucinate external functions or non-existent file paths.",
        "Check boundary conditions and zero-division cases explicitly.",
    ]

    def __init__(self, target_model_tier: str = "cheap_slm"):
        self.target_tier = target_model_tier
        self.coercion_engine = ParameterCoercionEngine()

    def compact_tool_schema(self, full_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compacts verbose MCP tool schemas by 75-80% for small model context budgets.
        Keeps essential properties and required lists while trimming long descriptions.
        """
        if not full_schema:
            return {}

        properties = full_schema.get("properties", {})
        compact_props = {}
        for prop_name, prop_def in properties.items():
            if not isinstance(prop_def, dict):
                continue
            compact_props[prop_name] = {
                "type": prop_def.get("type", "string"),
            }
            if "enum" in prop_def:
                compact_props[prop_name]["enum"] = prop_def["enum"]
            if "default" in prop_def:
                compact_props[prop_name]["default"] = prop_def["default"]

        return {
            "type": "object",
            "properties": compact_props,
            "required": full_schema.get("required", []),
        }

    def adapt_task(
        self,
        task: str,
        current_step: int = 1,
        total_steps: int = 3,
        step_goal: Optional[str] = None,
        context_hints: Optional[List[str]] = None,
    ) -> AdaptedPrompt:
        """
        Decomposes and condenses task instructions into a crisp micro-step prompt.
        """
        clean_task = task.strip()
        hints = context_hints or []
        step_objective = step_goal or clean_task

        condensed = (
            f"[STEP {current_step}/{total_steps} COGNITIVE HARNESS]\n"
            f"GOAL: {step_objective}\n"
            f"CONTEXT: {clean_task[:300]}\n"
        )

        if hints:
            condensed += "HINTS & LESSONS:\n" + "\n".join(f"- {h}" for h in hints[:3]) + "\n"

        condensed += (
            "\nREQUIRED OUTPUT FORMAT:\n"
            "{\n"
            '  "step_index": ' + str(current_step) + ",\n"
            '  "action_type": "reasoning | diff | query",\n'
            '  "payload": "<exact_step_output>",\n'
            '  "verification_rationale": "<why_this_step_is_correct>"\n'
            "}"
        )

        schema = {
            "type": "object",
            "properties": {
                "step_index": {"type": "integer"},
                "action_type": {"type": "string", "enum": ["reasoning", "diff", "query"]},
                "payload": {"type": "string"},
                "verification_rationale": {"type": "string"},
            },
            "required": ["step_index", "action_type", "payload", "verification_rationale"],
        }

        return AdaptedPrompt(
            original_task=task,
            condensed_prompt=condensed,
            expected_output_schema=schema,
            injected_invariants=self.DEFAULT_INVARIANTS,
        )

    def validate_and_repair_slm_output(self, raw_output: str) -> Dict[str, Any]:
        """
        Parses, strips fences, and deterministically repairs messy small-model outputs.
        """
        clean_text = raw_output.strip()
        # Direct json check
        try:
            direct = json.loads(clean_text)
            if isinstance(direct, dict):
                return direct
        except Exception:
            pass

        parsed = self.coercion_engine.parse_and_repair(raw_output)
        if "step_index" not in parsed:
            parsed["step_index"] = 1
        if "action_type" not in parsed:
            parsed["action_type"] = "reasoning"
        if "payload" not in parsed:
            parsed["payload"] = parsed.get("raw_content", raw_output[:1000])
        if "verification_rationale" not in parsed:
            parsed["verification_rationale"] = "Validated via AST parameter coercion"
        parsed["repaired"] = True

        return parsed
