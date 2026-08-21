"""
Local Workflow Value & Observability Reporting (WS9 / Phase 2).
Generates human-readable and structured value summaries without retaining raw code or secrets.
"""

from __future__ import annotations

from core.api.schemas import EliteVerifyResponse
from core.contracts.models import TaskContract


def generate_workflow_value_report(
    contract: TaskContract,
    verify_response: EliteVerifyResponse,
    network_requests: int = 0,
    retained_raw_prompt: bool = False,
) -> str:
    """Formats a clear, honest value scorecard for user terminals and logs."""
    total_reqs = len(contract.requirements)
    passed = verify_response.passed_count
    failed = verify_response.failed_count
    unknown = verify_response.unknown_count

    lines = [
        "Elite verification summary",
        f"- {total_reqs} requirements: {passed} PASS, {failed} FAIL, {unknown} UNKNOWN",
    ]

    if failed > 0:
        lines.append(f"- Prevented completion: {failed} requirement(s) failed verification")
    elif unknown > 0:
        lines.append(f"- Completion held: {unknown} requirement(s) have UNKNOWN verification status")
    else:
        lines.append("- Completion status: VERIFIED PASS")

    lines.append(f"- Local overhead: {verify_response.duration_ms:.2f} ms")
    lines.append(f"- Network requests: {network_requests}")
    lines.append(f"- Raw prompt retained: {'yes' if retained_raw_prompt else 'no'}")

    return "\n".join(lines)
