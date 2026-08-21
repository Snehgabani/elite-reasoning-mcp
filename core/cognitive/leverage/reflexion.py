# src/leverage/reflexion.py
import os
from typing import Any, Dict


class ReflexionReport:
    def __init__(self, failure_summary: str, root_cause_hypothesis: str, minimal_patch_plan: str, next_verification_command: str, lesson: str):
        self.failure_summary = failure_summary
        self.root_cause_hypothesis = root_cause_hypothesis
        self.minimal_patch_plan = minimal_patch_plan
        self.next_verification_command = next_verification_command
        self.lesson = lesson

    def to_markdown(self) -> str:
        return f"""## Reflexion
FAILURE:
{self.failure_summary}

ROOT CAUSE:
{self.root_cause_hypothesis}

MINIMAL PATCH:
{self.minimal_patch_plan}

NEXT TEST:
{self.next_verification_command}

LESSON:
{self.lesson}
"""

async def analyze_failure(task: str, candidate_content: str, verifier_output: str) -> ReflexionReport:
    f_sum = verifier_output.strip().split("\n")[0] if verifier_output else "Unknown execution failure"
    if "SyntaxError" in verifier_output:
        rc = "Syntax error in python code block (missing colon, parenthesis, or keyword typo)."
        patch = "Fix syntax error at specified line number."
        lesson = "Validate syntax with ast.parse before submitting code block."
    elif "ZeroDivisionError" in verifier_output or "division by zero" in verifier_output.lower():
        rc = "Attempted division by zero without guard condition."
        patch = "Add explicit `if divisor == 0: return None` guard check."
        lesson = "Always handle zero denominator in division functions."
    elif "ValueError" in verifier_output:
        rc = "Invalid parameter value passed without input validation."
        patch = "Add explicit range/sign parameter validation."
        lesson = "Validate numeric parameters at function entry points."
    else:
        rc = "Assertion failure or unhandled edge case."
        patch = "Update conditional logic to handle boundary conditions."
        lesson = "Ensure boundary cases (empty lists, negative numbers) are explicitly handled."

    return ReflexionReport(
        failure_summary=f_sum,
        root_cause_hypothesis=rc,
        minimal_patch_plan=patch,
        next_verification_command="pytest tests/golden -q",
        lesson=lesson
    )

async def reflexion_repair(task: str, candidate_content: str, verifier_output: str, max_attempts: int = 2) -> Dict[str, Any]:
    report = await analyze_failure(task, candidate_content, verifier_output)
    
    # Save lesson to memory file
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    lesson_path = os.path.join(base_dir, ".ai", "memory", "lessons.md")
    try:
        os.makedirs(os.path.dirname(lesson_path), exist_ok=True)
        with open(lesson_path, "a", encoding="utf-8") as f:
            f.write(f"\n- TASK: {task[:50]}\n  LESSON: {report.lesson}\n")

    except Exception as exc:
        # Explicit non-fatal exception suppression
        _ = str(exc)

    return {
        "report": report.to_markdown(),
        "patch_plan": report.minimal_patch_plan,
        "lesson": report.lesson,
        "attempts": 1
    }
