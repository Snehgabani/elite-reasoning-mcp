from core.contracts.models import Requirement, RequirementKind
from core.verification.models import Evidence, VerificationStatus
from core.verification.registry import GLOBAL_VERIFIER_REGISTRY


def test_stale_evidence_invalidation():
    req = Requirement(
        id="REQ-SEC-01",
        kind=RequirementKind.SECURITY,
        source_text="verify evidence matching draft",
        interpretation="Evidence must match draft digest",
        verifier="evidence_completeness_verifier",
    )

    current_content = "def calculate_tax(amount): return amount * 0.2"
    old_content = "def calculate_tax(amount): return amount * 0.15"

    current_digest = Evidence.compute_subject_digest(current_content)
    old_digest = Evidence.compute_subject_digest(old_content)

    valid_ev = Evidence(
        id="EV-1",
        kind="test_run",
        producer="pytest",
        subject_digest=current_digest,
        payload={"exit_code": 0},
    )

    stale_ev = Evidence(
        id="EV-2",
        kind="test_run",
        producer="pytest",
        subject_digest=old_digest,
        payload={"exit_code": 0},
    )

    # Valid evidence -> PASS
    res_pass = GLOBAL_VERIFIER_REGISTRY.verify_requirement(req, current_content, evidence_records=[valid_ev])
    assert res_pass.status == VerificationStatus.PASS

    # Stale evidence -> FAIL with explicit explanation
    res_fail = GLOBAL_VERIFIER_REGISTRY.verify_requirement(req, current_content, evidence_records=[stale_ev])
    assert res_fail.status == VerificationStatus.FAIL
    assert "Stale evidence detected" in res_fail.reason
