"""
Deterministic Invariant Gates & Zero-Escape Verification Engine for MIX MCP.
Executes pure Python (0ms LLM latency) static analysis, AST validation, security audits,
and cryptographic diff integrity verification.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
import os
import re
import sqlite3
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ValidationResult:
    """Standardized validation outcome across all deterministic gates."""
    passed: bool
    score: float  # 0.0 to 1.0
    issues: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "score": round(self.score, 4),
            "issues": self.issues,
            "metadata": self.metadata,
        }


# ============================================================================
# 1. POLYGLOT SYNTAX & AST VALIDATOR
# ============================================================================

def validate_syntax(code: str, language: str = "python") -> ValidationResult:
    """
    Validates code syntax across multiple languages with 0ms LLM latency.
    Supports Python AST, JSON, SQLite SQL, and JavaScript/TypeScript balanced brackets.
    """
    if not code or not code.strip():
        return ValidationResult(passed=False, score=0.0, issues=["Empty code candidate"])

    lang = (language or "python").lower().strip()

    # --- Python AST Validation ---
    if lang in ("python", "py"):
        try:
            tree = ast.parse(code)
            issues = []
            penalty = 0.0

            # Inspect AST for common anti-patterns
            for node in ast.walk(tree):
                # Bare except clause
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    penalty += 0.20
                    issues.append("Code Quality: Bare 'except:' clause masks critical exceptions.")
                # Blocking time.sleep inside async functions
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr == "sleep" and getattr(node.func.value, "id", "") == "time":
                        for parent in ast.walk(tree):
                            if isinstance(parent, ast.AsyncFunctionDef) and node in ast.walk(parent):
                                penalty += 0.25
                                issues.append("Concurrency Hazard: Blocking 'time.sleep()' inside async function (use 'await asyncio.sleep').")

            score = max(0.0, 1.0 - penalty)
            return ValidationResult(
                passed=(score >= 0.80 and len(issues) == 0),
                score=score,
                issues=issues,
                metadata={"language": "python", "ast_nodes": sum(1 for _ in ast.walk(tree))}
            )
        except SyntaxError as e:
            return ValidationResult(
                passed=False,
                score=0.0,
                issues=[f"Python SyntaxError: {e.msg} (line {e.lineno}, col {e.offset})"],
                metadata={"language": "python", "lineno": e.lineno, "offset": e.offset}
            )

    # --- JSON Validation ---
    elif lang in ("json",):
        try:
            parsed = json.loads(code)
            return ValidationResult(
                passed=True,
                score=1.0,
                issues=[],
                metadata={"language": "json", "type": type(parsed).__name__}
            )
        except json.JSONDecodeError as e:
            return ValidationResult(
                passed=False,
                score=0.0,
                issues=[f"JSON SyntaxError: {e.msg} (line {e.lineno}, col {e.colno})"],
                metadata={"language": "json", "lineno": e.lineno}
            )

    # --- SQLite SQL Validation ---
    elif lang in ("sql",):
        try:
            conn = sqlite3.connect(":memory:")
            conn.execute(f"EXPLAIN {code}")
            conn.close()
            return ValidationResult(passed=True, score=1.0, issues=[], metadata={"language": "sql"})
        except sqlite3.OperationalError as e:
            err_msg = str(e).lower()
            # Missing table/column is schema-dependent, not a syntax failure
            if any(term in err_msg for term in ("no such table", "no such column", "no such view")):
                return ValidationResult(passed=True, score=0.95, issues=[], metadata={"language": "sql", "note": "Valid syntax (schema unresolved)"})
            return ValidationResult(passed=False, score=0.0, issues=[f"SQL SyntaxError: {e}"], metadata={"language": "sql"})

    # --- JavaScript / TypeScript Bracket & Structure Validation ---
    elif lang in ("javascript", "typescript", "js", "ts", "jsx", "tsx"):
        brackets = {"(": ")", "{": "}", "[": "]"}
        stack: List[str] = []
        in_string: Optional[str] = None
        escaped = False

        for idx, char in enumerate(code):
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char in ("'", '"', "`"):
                if in_string == char:
                    in_string = None
                elif in_string is None:
                    in_string = char
                continue
            if in_string is not None:
                continue

            if char in brackets:
                stack.append(brackets[char])
            elif char in brackets.values():
                if not stack or stack.pop() != char:
                    return ValidationResult(
                        passed=False,
                        score=0.0,
                        issues=[f"JS/TS SyntaxError: Unbalanced or mismatched bracket '{char}' at char {idx}"],
                        metadata={"language": lang, "char_index": idx}
                    )

        if stack:
            return ValidationResult(
                passed=False,
                score=0.0,
                issues=[f"JS/TS SyntaxError: Unclosed bracket (expected '{stack[-1]}')"],
                metadata={"language": lang}
            )
        return ValidationResult(passed=True, score=1.0, issues=[], metadata={"language": lang})

    # Default fallback for plaintext / unknown formats
    return ValidationResult(passed=True, score=0.90, issues=[], metadata={"language": lang, "status": "unvalidated_text"})


# ============================================================================
# 2. OWASP & SECURITY INVARIANT GATE
# ============================================================================

def validate_security_invariants(code: str) -> ValidationResult:
    """
    Evaluates Python AST and code text against OWASP/CWE safety invariants.
    Detects dynamic code execution (eval/exec), dangerous subprocesses, and credential leaks.
    """
    if not code:
        return ValidationResult(passed=True, score=1.0)

    issues: List[str] = []
    penalty = 0.0

    # 1. Regex text scan for dangerous system commands
    dangerous_patterns = [
        (r"os\.system\s*\(\s*['\"]rm\s+-rf", "Fatal Security Violation: 'rm -rf' command in os.system"),
        (r"shutil\.rmtree\s*\(\s*['\"]\/['\"]", "Fatal Security Violation: Root directory deletion attempt"),
        (r"subprocess\.call\s*\(\s*['\"]rm\s+-rf", "Fatal Security Violation: 'rm -rf' command in subprocess"),
        (r"(ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{48})", "Security Invariant: Hardcoded plaintext API credential/token detected"),
    ]
    for pattern, desc in dangerous_patterns:
        if re.search(pattern, code, re.IGNORECASE):
            penalty += 1.0
            issues.append(desc)

    # 2. AST inspection for dynamic code execution
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # eval() or exec() or compile()
                if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec", "compile", "__import__"):
                    penalty += 0.50
                    issues.append(f"Security Invariant: Forbidden dynamic code execution via '{node.func.id}()'")
    except SyntaxError:
        # Defer syntax issues to validate_syntax
        pass

    score = max(0.0, 1.0 - penalty)
    passed = (score >= 0.90 and len(issues) == 0)
    return ValidationResult(passed=passed, score=score, issues=issues)


# ============================================================================
# 3. MATHEMATICAL & LOGICAL INVARIANT GATE
# ============================================================================

def validate_math_invariants(text: str) -> ValidationResult:
    """
    Scans text for mathematical and logical inconsistencies:
    division-by-zero, contradictory inequalities, unbalanced math brackets, and NaN fallacies.
    """
    if not text:
        return ValidationResult(passed=True, score=1.0)

    penalty = 0.0
    issues: List[str] = []

    # Division by zero
    if re.search(r"/\s*0(?![0-9])", text) or re.search(r"divid\w*\s+(?:\w+\s+)*by\s+zero", text, re.IGNORECASE):
        penalty += 0.50
        issues.append("Math Invariant Error: Unchecked division by zero detected.")

    # Unbalanced mathematical brackets
    brackets = {"(": ")", "[": "]", "{": "}"}
    stack: List[str] = []
    for char in text:
        if char in brackets.keys():
            stack.append(char)
        elif char in brackets.values():
            if not stack or brackets[stack.pop()] != char:
                penalty += 0.20
                issues.append("Math Invariant Warning: Unbalanced bracket in mathematical notation.")
                break

    # Contradictory inequalities (e.g. x > y and y > x)
    if re.search(r"(\w+)\s*>\s*(\w+).*\2\s*>\s*\1", text):
        penalty += 0.50
        issues.append("Logical Contradiction: Circular/contradictory inequality detected.")

    # NaN self-equality fallacy
    if re.search(r"\bfloat\('nan'\)\s*==\s*float\('nan'\)", text):
        penalty += 0.35
        issues.append("Math Invariant Error: NaN self-equality fallacy (NaN != NaN).")

    score = max(0.0, 1.0 - penalty)
    passed = (score >= 0.85 and len(issues) == 0)
    return ValidationResult(passed=passed, score=score, issues=issues)


# ============================================================================
# 4. DIFF INTEGRITY & CRYPTOGRAPHIC AUTHORIZATION GATE
# ============================================================================

def generate_diff_hmac(file_path: str, replacement: str, secret_key: bytes) -> str:
    """Generates an HMAC-SHA256 authorization token bound to canonical path & replacement hash."""
    norm_path = os.path.abspath(file_path)
    rep_hash = hashlib.sha256(replacement.encode("utf-8")).hexdigest()
    msg = f"{norm_path}:{rep_hash}".encode("utf-8")
    return hmac.new(secret_key, msg, hashlib.sha256).hexdigest()


def validate_diff_integrity(
    file_path: str,
    original: str,
    replacement: str,
    token: str,
    secret_key: bytes,
    verify_spliced_ast: bool = True
) -> ValidationResult:
    """
    The Ironclad Filesystem Gatekeeper:
    1. Blocks path traversals ('..').
    2. Validates HMAC authorization token.
    3. Verifies target file exists and contains original snippet.
    4. Simulates spliced file in RAM and verifies that AST remains valid before allowing write.
    """
    issues: List[str] = []

    # 1. Path traversal check
    if ".." in file_path or not os.path.isabs(file_path):
        return ValidationResult(passed=False, score=0.0, issues=["Security Error: Non-absolute or traversing file path"])

    norm_path = os.path.abspath(file_path)

    # 2. Cryptographic token verification
    expected_token = generate_diff_hmac(norm_path, replacement, secret_key)
    if not hmac.compare_digest(token, expected_token):
        return ValidationResult(
            passed=False,
            score=0.0,
            issues=["Authorization Error: Invalid or missing HMAC execution token (Execution Blocked)"]
        )

    # 3. File existence check
    if not os.path.exists(norm_path):
        return ValidationResult(passed=False, score=0.0, issues=[f"Filesystem Error: Target file '{norm_path}' does not exist"])

    # 4. Target snippet match check
    try:
        with open(norm_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return ValidationResult(passed=False, score=0.0, issues=[f"Filesystem Error: Could not read target file: {e}"])

    if original not in content:
        return ValidationResult(
            passed=False,
            score=0.0,
            issues=["Diff Error: 'original' snippet does not match exact content in target file"]
        )

    # 5. Spliced In-Memory AST Pre-flight
    if verify_spliced_ast and norm_path.endswith(".py"):
        spliced_content = content.replace(original, replacement, 1)
        syntax_res = validate_syntax(spliced_content, "python")
        if not syntax_res.passed:
            return ValidationResult(
                passed=False,
                score=0.0,
                issues=[f"Diff Pre-flight Error: Splicing this diff will break target file AST: {syntax_res.issues}"]
            )

    return ValidationResult(passed=True, score=1.0, issues=[])


def apply_verified_diff(file_path: str, original: str, replacement: str) -> Tuple[bool, str]:
    """
    Atomically writes a verified diff to disk using NamedTemporaryFile and atomic os.replace.
    Guarantees no partial writes or file corruptions.
    """
    norm_path = os.path.abspath(file_path)
    try:
        with open(norm_path, "r", encoding="utf-8") as f:
            content = f.read()

        if original not in content:
            return False, "Target content snippet not found in file."

        new_content = content.replace(original, replacement, 1)
        dir_name = os.path.dirname(norm_path)

        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tmp:
            tmp.write(new_content)
            tmp_name = tmp.name

        os.replace(tmp_name, norm_path)
        return True, f"Successfully applied atomic diff to '{norm_path}'."
    except Exception as e:
        return False, f"Atomic disk write failed: {e}"
