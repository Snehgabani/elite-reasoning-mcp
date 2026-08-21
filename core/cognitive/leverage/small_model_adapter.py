"""
Small Model Cognitive Adapter & Schema Constrainer.
Optimizes prompt schemas, eliminates ambiguity, and injects minimal 1-step
scaffolding for cheap/low-intelligence language models (e.g. 7B/8B, GPT-4o-mini, Flash).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


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
    instructions with explicit output schema constraints.
    """

    DEFAULT_INVARIANTS = [
        "Return STRICT JSON only. Do not include markdown code block backticks or conversational text.",
        "Execute strictly ONE logical step at a time.",
        "Never hallucinate external functions or non-existent file paths.",
        "Check boundary conditions and zero-division cases explicitly.",
    ]

    def __init__(self, target_model_tier: str = "cheap_slm"):
        self.target_tier = target_model_tier

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
        Parses and deterministically repairs messy small-model outputs (stripping markdown, fixing trailing commas).
        """
        clean_text = raw_output.strip()

        # 1. Strip markdown fences if present
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_text, flags=re.I)
        if fence_match:
            clean_text = fence_match.group(1).strip()

        # 2. Try direct JSON parsing
        try:
            return json.loads(clean_text)
        except json.JSONDecodeError:
            pass

        # 3. Heuristic JSON repair (trailing commas, quotes)
        repaired = re.sub(r",\s*([\]}])", r"\1", clean_text)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # 4. Fallback structured extraction
        return {
            "step_index": 1,
            "action_type": "reasoning",
            "payload": clean_text[:1000],
            "verification_rationale": "Extracted via small model heuristic fallback parser",
            "repaired": True,
        }
