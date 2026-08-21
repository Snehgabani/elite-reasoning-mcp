# src/leverage/verifier.py
import subprocess
import tempfile
import ast
import os
from typing import Optional, List, Dict, Any

class VerificationResult:
    def __init__(self, passed: bool, score: float, output: str, failure_type: Optional[str] = None, evidence: Optional[Dict[str, Any]] = None):
        self.passed = passed
        self.score = score
        self.output = output
        self.failure_type = failure_type
        self.evidence = evidence or {}

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "score": self.score,
            "output": self.output,
            "failure_type": self.failure_type,
            "evidence": self.evidence
        }

async def verify_code_candidate(
    task: str,
    candidate_code: str,
    test_command: Optional[str] = None,
    sandbox_mode: str = "local"
) -> VerificationResult:
    if not candidate_code.strip():
        return VerificationResult(
            passed=False,
            score=0.0,
            output="Empty candidate code",
            failure_type="empty_code"
        )

    # 1. Syntax check
    try:
        ast.parse(candidate_code)
    except SyntaxError as e:
        return VerificationResult(
            passed=False,
            score=0.0,
            output=f"SyntaxError: {str(e)}",
            failure_type="syntax_error"
        )

    # 2. Test command execution if provided
    if test_command:
        try:
            res = subprocess.run(test_command.split(), capture_output=True, text=True, timeout=30)
            passed = (res.returncode == 0)
            return VerificationResult(
                passed=passed,
                score=1.0 if passed else 0.0,
                output=res.stdout + res.stderr,
                failure_type=None if passed else "test_failure"
            )
        except Exception as e:
            return VerificationResult(
                passed=False,
                score=0.0,
                output=str(e),
                failure_type="execution_error"
            )

    # 3. Default execution check
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
        tmp.write(candidate_code)
        tmp_path = tmp.name

    try:
        res = subprocess.run(["python", tmp_path], capture_output=True, text=True, timeout=10)
        passed = (res.returncode == 0)
        return VerificationResult(
            passed=passed,
            score=1.0 if passed else 0.3,
            output=res.stdout if passed else res.stderr,
            failure_type=None if passed else "runtime_error"
        )
    except Exception as e:
        return VerificationResult(
            passed=False,
            score=0.0,
            output=str(e),
            failure_type="timeout_error"
        )
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

async def verify_non_code_candidate(
    task: str,
    candidate_answer: str,
    rubric: List[str]
) -> VerificationResult:
    if not candidate_answer.strip():
        return VerificationResult(
            passed=False,
            score=0.0,
            output="Empty response",
            failure_type="empty_response"
        )

    matched = 0
    c_lower = candidate_answer.lower()
    for item in rubric:
        item_words = item.lower().replace("_", " ").split()
        if any(w in c_lower for w in item_words):
            matched += 1

    score = round(matched / len(rubric), 2) if rubric else 1.0
    passed = score >= 0.75

    return VerificationResult(
        passed=passed,
        score=score,
        output=f"Rubric match {matched}/{len(rubric)} items",
        failure_type=None if passed else "rubric_failure"
    )
