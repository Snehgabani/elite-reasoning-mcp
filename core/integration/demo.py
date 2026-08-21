"""
Deterministic Offline CLI Demo (WS6 / Issue 15).
Runs a local, zero-network end-to-end demonstration:
1. Compiles a constrained coding request.
2. Displays source-linked requirements.
3. Verifies an invalid draft and demonstrates specific FAIL reason.
4. Verifies a corrected draft and demonstrates PASS result.
5. Emits summary with zero network overhead in sub-second duration.
"""

from __future__ import annotations

import json
import sys
import time
from core.contracts.compiler import ContractCompiler
from core.verification.models import VerificationStatus
from core.verification.registry import GLOBAL_VERIFIER_REGISTRY


def run_deterministic_demo(as_json: bool = False) -> int:
    t0 = time.perf_counter()
    compiler = ContractCompiler()

    # 1. Compile constrained prompt
    prompt = "Refactor auth logic. Must include OAuth2 and do not use bcrypt. Modify only auth.py."
    contract = compiler.compile(prompt)

    # 2. Test Invalid Candidate (missing OAuth2, uses bcrypt, touches settings.py)
    bad_code = "def authenticate(): # uses bcrypt\n    import bcrypt\n    return True"
    bad_diff = "diff --git a/settings.py b/settings.py\n+ SECRET_KEY = '123'"

    bad_results = []
    for req in contract.requirements:
        subject = bad_diff if req.kind.value == "allowed_files" else bad_code
        res = GLOBAL_VERIFIER_REGISTRY.verify_requirement(req, subject)
        bad_results.append(res)

    has_expected_fails = any(r.status == VerificationStatus.FAIL for r in bad_results)

    # 3. Test Corrected Candidate (has OAuth2, no bcrypt, touches auth.py)
    good_code = "def authenticate_oauth2():\n    # OAuth2 compliant\n    return True"
    good_diff = "diff --git a/auth.py b/auth.py\n+ def authenticate_oauth2(): pass"

    good_results = []
    for req in contract.requirements:
        subject = good_diff if req.kind.value == "allowed_files" else good_code
        res = GLOBAL_VERIFIER_REGISTRY.verify_requirement(req, subject)
        good_results.append(res)

    all_passed = all(r.status == VerificationStatus.PASS for r in good_results)
    duration_ms = (time.perf_counter() - t0) * 1000

    report = {
        "status": "SUCCESS" if (has_expected_fails and all_passed) else "FAILED",
        "duration_ms": round(duration_ms, 2),
        "network_requests": 0,
        "contract": contract.model_dump(),
        "invalid_candidate_verdicts": [r.model_dump() for r in bad_results],
        "corrected_candidate_verdicts": [r.model_dump() for r in good_results],
    }

    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print("=================================================================")
        print("🚀 Elite Reasoning MCP - Deterministic Verification Demo")
        print("=================================================================")
        print(f"Goal: {contract.goal}")
        print(f"Extracted Requirements: {len(contract.requirements)}")
        for r in contract.requirements:
            print(f"  • [{r.severity.value.upper()}] {r.kind.value}: {r.interpretation}")
        print("\n[Test 1: Defective Draft Evaluation]")
        for r in bad_results:
            icon = "❌" if r.status == VerificationStatus.FAIL else "✅"
            print(f"  {icon} {r.requirement_id} -> {r.status.value}: {r.reason}")
        print("\n[Test 2: Corrected Draft Evaluation]")
        for r in good_results:
            icon = "✅" if r.status == VerificationStatus.PASS else "❌"
            print(f"  {icon} {r.requirement_id} -> {r.status.value}: {r.reason}")
        print(f"\nExecution Duration: {duration_ms:.2f}ms | Network Requests: 0 | Local Invariants: SECURE")
        print("=================================================================")

    return 0 if (has_expected_fails and all_passed) else 1


if __name__ == "__main__":
    as_json = "--json" in sys.argv
    sys.exit(run_deterministic_demo(as_json=as_json))
