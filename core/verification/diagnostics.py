"""
Reflexion Minimal Diagnostic AST Slicer (Shinn et al., NeurIPS 2023).
Extracts concise, minimal failure slices from test failures and AST errors,
reducing repair token consumption and eliminating hallucinated fix loops.
"""

from __future__ import annotations

import re
from typing import Optional
from pydantic import BaseModel


class DiagnosticSlice(BaseModel):
    failing_file: Optional[str] = None
    failing_line_number: Optional[int] = None
    error_type: str
    error_message: str
    minimal_code_context: Optional[str] = None
    suggested_invariant_fix: str
    sliced_traceback: Optional[str] = None
    schema_version: str = "1.1.0"


def slice_raw_traceback(raw_trace: str, max_frames: int = 3, max_chars: int = 1500) -> str:
    """Prunes runtime framework internal frames and caps traceback size to protect context budget."""
    if not raw_trace:
        return ""
    lines = raw_trace.splitlines()
    filtered_lines: list[str] = []

    # Filter out pytest, site-packages, uvicorn, and importlib runtime boilerplate
    for line in lines:
        if any(skip in line for skip in ("/site-packages/", "<frozen ", "/pytest/", "/pluggy/")):
            continue
        filtered_lines.append(line)

    result = "\n".join(filtered_lines[-max_frames * 4 :]) if filtered_lines else "\n".join(lines[-10:])
    return result[-max_chars:].strip()


def extract_diagnostic_slice(error_text: str, source_code: Optional[str] = None) -> DiagnosticSlice:
    """Parses tracebacks or error messages into a structured, minimal diagnostic slice."""
    # Match standard python traceback patterns
    line_match = re.findall(r'File "([^"]+)", line (\d+)(?:, in (\w+))?', error_text)
    err_match = re.search(r"([A-Za-z]+Error|[A-Za-z]+Exception):\s*(.*)", error_text)

    # Prefer user code frame over framework internal frame
    user_frames = [
        f for f in line_match if not any(skip in f[0] for skip in ("/site-packages/", "<frozen ", "/pytest/"))
    ]
    target_frame = user_frames[-1] if user_frames else (line_match[-1] if line_match else None)

    file_name = target_frame[0] if target_frame else None
    line_num = int(target_frame[1]) if target_frame else None
    err_type = err_match.group(1) if err_match else "ExecutionError"
    err_msg = (
        err_match.group(2).strip()
        if err_match
        else error_text.strip().splitlines()[-1]
        if error_text.strip()
        else "Unknown error"
    )[:500]

    code_context = None
    if source_code and line_num:
        lines = source_code.splitlines()
        start = max(0, line_num - 2)
        end = min(len(lines), line_num + 2)
        code_context = "\n".join(f"{i + 1}: {lines[i]}" for i in range(start, end))

    fix_suggestion = f"Check invariant at line {line_num or 'unknown'} for {err_type}: {err_msg}"
    if "SyntaxError" in err_type:
        fix_suggestion = f"Fix syntax structure around line {line_num}: verify balanced brackets and colons."
    elif "KeyError" in err_type or "IndexError" in err_type:
        fix_suggestion = f"Add boundary guard or .get() default before access at line {line_num}."

    return DiagnosticSlice(
        failing_file=file_name,
        failing_line_number=line_num,
        error_type=err_type,
        error_message=err_msg,
        minimal_code_context=code_context,
        suggested_invariant_fix=fix_suggestion,
        sliced_traceback=slice_raw_traceback(error_text),
    )
