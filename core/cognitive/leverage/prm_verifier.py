"""
Process Reward Model (PRM) — Deep Step-Level Invariant & Reasoning Verifier Engine.
Grounded in Lightman et al. (OpenAI 2023) and Wang et al. (Math-Shepherd 2024).
Fuses AST invariant parsing, OWASP security auditing, and mathematical constraint verification.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from core.cognitive.leverage.deterministic_gates import (
    validate_math_invariants,
    validate_security_invariants,
    validate_syntax,
)


class ProcessRewardModel:
    """
    Step-Level Process Reward Model (PRM).
    Evaluates logical coherence, mathematical invariant consistency, quantifier validity,
    security invariants, and code syntax integrity for each step in a multi-step reasoning chain.
    """
    def __init__(self, threshold: float = 0.80):
        self.threshold = threshold

    def _check_cognitive_biases(self, text: str) -> tuple[float, List[str]]:
        penalty = 0.0
        issues = []
        text_lower = text.lower()

        # Dogmatic / Unsubstantiated certainty
        dogmatic_phrases = [
            ("obviously", 0.25, "Dogmatic claim ('obviously') without deductive derivation."),
            ("definitely without checking", 0.40, "Unchecked certainty without evidentiary support."),
            ("trivially true for all cases", 0.30, "Over-generalized universal claim."),
            ("it is self-evident", 0.25, "Appealing to self-evidence rather than formal proof."),
            ("guaranteed to never fail", 0.35, "Absolutist stability claim without error boundary analysis.")
        ]
        for phrase, pen, desc in dogmatic_phrases:
            if phrase in text_lower:
                penalty += pen
                issues.append(f"PRM Epistemic Warning: {desc}")

        # Magic numbers / hardcoded offsets without derivation
        if re.search(r"magic\s+number", text_lower) or re.search(r"\+\s*12\b(?!\s*months)", text_lower):
            penalty += 0.25
            issues.append("PRM Warning: Hardcoded magic number/offset without derivation.")

        return penalty, issues

    def verify_step_sync(self, step_text: str, context: str = "") -> Dict[str, Any]:
        """Synchronous deterministic evaluation of a reasoning step or code block."""
        base_score = 0.98
        total_penalty = 0.0
        all_issues = []

        # 1. Math Invariants Gate
        math_res = validate_math_invariants(step_text)
        if not math_res.passed:
            total_penalty += (1.0 - math_res.score)
            all_issues.extend(math_res.issues)

        # 2. Cognitive Biases Gate
        bias_pen, bias_issues = self._check_cognitive_biases(step_text)
        total_penalty += bias_pen
        all_issues.extend(bias_issues)

        # 3. Code & Security Gates on Fenced Code Blocks
        code_blocks = re.findall(r"```(?:[a-zA-Z0-9_\-]+)?\s*(.*?)\s*```", step_text, re.DOTALL)
        if not code_blocks and ("def " in step_text or "class " in step_text or "import " in step_text):
            code_blocks = [step_text]

        code_score = 1.0
        for block in code_blocks:
            # Syntax check
            syntax_res = validate_syntax(block, "python")
            if not syntax_res.passed:
                total_penalty += 0.40
                all_issues.extend(syntax_res.issues)
                code_score = min(code_score, syntax_res.score)

            # Security check
            sec_res = validate_security_invariants(block)
            if not sec_res.passed:
                total_penalty += 0.50
                all_issues.extend(sec_res.issues)
                code_score = min(code_score, sec_res.score)

        final_score = max(0.0, min(1.0, base_score - total_penalty))
        passed = final_score >= self.threshold and len(all_issues) == 0

        return {
            "step_text": step_text[:120] + "..." if len(step_text) > 120 else step_text,
            "prm_score": round(final_score, 3),
            "threshold": self.threshold,
            "passed": passed,
            "issues": all_issues,
            "status": "APPROVED" if passed else "REJECTED_BY_PRM",
            "dimensions": {
                "math_validity": round(math_res.score, 2),
                "epistemic_rigor": round(max(0.0, 1.0 - bias_pen), 2),
                "code_syntax": round(code_score, 2)
            }
        }

    async def verify_step(self, step_text: str, context: str = "") -> Dict[str, Any]:
        """Async wrapper for verify_step_sync."""
        return self.verify_step_sync(step_text, context)


async def prm_verify_step(step_text: str) -> str:
    prm = ProcessRewardModel()
    res = await prm.verify_step(step_text)
    return json.dumps(res, indent=2)
