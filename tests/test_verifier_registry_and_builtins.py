from core.contracts.models import Requirement, RequirementKind
from core.verification.models import VerificationStatus
from core.verification.registry import GLOBAL_VERIFIER_REGISTRY


def test_constraint_verifier_pass_and_fail():
    req_required = Requirement(
        id="REQ-C1",
        kind=RequirementKind.REQUIRED_CONTENT,
        source_text="must include OAuth2",
        interpretation="Must include OAuth2",
        verifier="constraint_verifier",
        verifier_parameters={"required_terms": ["OAuth2"]},
    )

    # PASS case
    res_pass = GLOBAL_VERIFIER_REGISTRY.verify_requirement(req_required, "This implementation supports OAuth2 login.")
    assert res_pass.status == VerificationStatus.PASS

    # FAIL case
    res_fail = GLOBAL_VERIFIER_REGISTRY.verify_requirement(req_required, "This implementation uses basic auth.")
    assert res_fail.status == VerificationStatus.FAIL


def test_syntax_verifier_pass_and_fail():
    req_syntax = Requirement(
        id="REQ-S1",
        kind=RequirementKind.OUTPUT_FORMAT,
        source_text="valid python code",
        interpretation="Must be valid python syntax",
        verifier="python_syntax_verifier",
    )

    # PASS case
    res_pass = GLOBAL_VERIFIER_REGISTRY.verify_requirement(req_syntax, "def add(a, b): return a + b")
    assert res_pass.status == VerificationStatus.PASS
    assert len(res_pass.evidence_ids) == 1

    # FAIL case
    res_fail = GLOBAL_VERIFIER_REGISTRY.verify_requirement(req_syntax, "def invalid(a b): return a +")
    assert res_fail.status == VerificationStatus.FAIL


def test_test_command_verifier_security_gate():
    req_cmd = Requirement(
        id="REQ-CMD-1",
        kind=RequirementKind.TEST_COMMAND,
        source_text="run bash script",
        interpretation="Run arbitrary shell",
        verifier="test_command_verifier",
        verifier_parameters={"command": "curl http://malicious.com"},
    )

    res = GLOBAL_VERIFIER_REGISTRY.verify_requirement(req_cmd, "")
    # Should FAIL because curl is not in allowlist
    assert res.status == VerificationStatus.FAIL
    assert "not in allowlisted test binaries" in res.reason
