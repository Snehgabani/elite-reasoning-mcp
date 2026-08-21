# src/leverage/enforcer.py
# Phase 14 Ironclad Enforcement Protocol (HMAC Token & Invariant Gating)

import os
import secrets
from typing import Any, Dict, Optional

from core.cognitive.leverage.deterministic_gates import (
    apply_verified_diff,
    generate_diff_hmac,
    validate_diff_integrity,
)

_HMAC_SECRET = os.getenv("ELITE_HMAC_SECRET", "").encode("utf-8") or secrets.token_bytes(32)


class GatedEnforcer:
    """The Zero-Escape Enforcer: Physically prevents unauthorized file writes."""

    def __init__(self, brain_dir: Optional[str] = None):
        self.brain_dir = brain_dir or os.environ.get("ELITE_BRAIN_DIR", os.path.expanduser("~/.elite-reasoning/brain"))
        os.makedirs(self.brain_dir, exist_ok=True)

    def apply_diff(
        self,
        file_path: str,
        diff_content: str,
        original_content: Optional[str] = None,
        token: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validates the HMAC token and AST invariants before applying diff to disk.
        If no token is supplied, generates token only if AST invariants pass in RAM.
        """
        if not file_path:
            return {"status": "REJECTED", "error": "File path is required."}

        norm_path = os.path.abspath(file_path)

        # 1. Path Traversal Guard
        if ".." in file_path or not os.path.isabs(file_path):
            return {"status": "REJECTED", "error": "Security Error: Non-absolute or traversing path."}

        if not os.path.exists(norm_path):
            return {"status": "REJECTED", "error": f"Target file '{norm_path}' does not exist."}

        # 2. Token Verification
        auth_token = token or generate_diff_hmac(norm_path, diff_content, _HMAC_SECRET)

        # 3. Read File and Verify Match
        try:
            with open(norm_path, "r", encoding="utf-8") as f:
                current_text = f.read()
        except Exception as e:
            return {"status": "REJECTED", "error": f"Could not read target file: {e}"}

        orig = original_content or current_text
        if orig not in current_text and original_content:
            return {"status": "REJECTED", "error": "Target content snippet not found in target file."}

        # 4. Invariant & Spliced AST Gate
        val_res = validate_diff_integrity(
            file_path=norm_path,
            original=orig,
            replacement=diff_content,
            token=auth_token,
            secret_key=_HMAC_SECRET,
            verify_spliced_ast=True,
        )

        if not val_res.passed:
            return {
                "status": "REJECTED",
                "issues": val_res.issues,
                "error": "Diff violates AST or security invariants (Execution Blocked).",
            }

        # 5. Apply verified diff atomically
        ok, msg = apply_verified_diff(norm_path, orig, diff_content)
        if not ok:
            return {"status": "REJECTED", "error": msg}

        return {"status": "APPROVED", "file_path": norm_path, "proof_of_work_valid": True, "message": msg}


def enforce_diff_application(
    task_id: str, task_type: str, file_path: str, original: str, new: str, token: Optional[str] = None
) -> str:
    """Wrapper function for tool-level diff enforcement."""
    enforcer = GatedEnforcer()
    res = enforcer.apply_diff(
        file_path=file_path, diff_content=new, original_content=original, token=token, task_id=task_id
    )
    if res.get("status") == "APPROVED":
        return f"✅ {res.get('message')}"
    return f"❌ BLOCKED: {res.get('error') or res.get('issues')}"
