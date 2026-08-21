from core.contracts.models import Requirement, RequirementKind
from core.verification.models import VerificationStatus
from core.verification.type_checker import TypeInvariantVerifier


def test_type_invariant_verifier():
    verifier = TypeInvariantVerifier()
    req = Requirement(
        id="REQ-TYPE-1",
        kind=RequirementKind.COMPATIBILITY,
        source_text="must have type annotations",
        interpretation="All public functions have explicit return type annotations",
        verifier="type_invariant_verifier",
    )

    # 1. Missing return type
    bad_code = """
def calculate_tax(amount: float):
    return amount * 0.2
"""
    res_bad = verifier.verify(req, bad_code)
    assert res_bad.status == VerificationStatus.FAIL
    assert "calculate_tax" in res_bad.reason

    # 2. Typed function
    good_code = """
def calculate_tax(amount: float) -> float:
    return amount * 0.2
"""
    res_good = verifier.verify(req, good_code)
    assert res_good.status == VerificationStatus.PASS
