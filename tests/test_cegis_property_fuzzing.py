from core.contracts.models import Requirement, RequirementKind
from core.verification.cegis import CEGISPropertyVerifier
from core.verification.models import VerificationStatus


def test_cegis_property_fuzzer():
    verifier = CEGISPropertyVerifier()
    req = Requirement(
        id="REQ-CEGIS-1",
        kind=RequirementKind.ROBUSTNESS,
        source_text="must be robust against edge cases",
        interpretation="Handle empty collections and bounds",
        verifier="cegis_property_verifier",
    )

    # 1. Unsafe draft (unprotected items[0])
    unsafe_code = """
def get_first_item(items):
    return items[0]
"""
    res_unsafe = verifier.verify(req, unsafe_code)
    assert res_unsafe.status == VerificationStatus.FAIL
    assert "items = []" in res_unsafe.reason

    # 2. Safe draft (guarded)
    safe_code = """
def get_first_item(items):
    if not items:
        return None
    return items[0]
"""
    res_safe = verifier.verify(req, safe_code)
    assert res_safe.status == VerificationStatus.PASS
