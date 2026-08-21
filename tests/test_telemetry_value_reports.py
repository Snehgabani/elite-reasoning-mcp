from core.api.schemas import EliteVerifyResponse
from core.contracts.compiler import ContractCompiler
from core.telemetry.reports import generate_workflow_value_report
from core.verification.models import VerificationStatus


def test_workflow_value_report_generation():
    compiler = ContractCompiler()
    contract = compiler.compile("Refactor auth logic. Must include OAuth2. Modify only auth.py.")

    verify_resp = EliteVerifyResponse(
        overall_status=VerificationStatus.PASS,
        passed_count=2,
        failed_count=0,
        unknown_count=0,
        not_checked_count=0,
        duration_ms=0.86,
    )

    report = generate_workflow_value_report(
        contract=contract,
        verify_response=verify_resp,
        network_requests=0,
        retained_raw_prompt=False,
    )

    assert "Elite verification summary" in report
    assert "2 PASS, 0 FAIL, 0 UNKNOWN" in report
    assert "Completion status: VERIFIED PASS" in report
    assert "Local overhead: 0.86 ms" in report
    assert "Network requests: 0" in report
    assert "Raw prompt retained: no" in report
