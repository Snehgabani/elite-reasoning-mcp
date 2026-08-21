from core.api.schemas import ElitePrepareResponse, EliteVerifyResponse
from core.contracts.compiler import ContractCompiler
from core.verification.models import VerificationStatus


def test_api_schemas_versioning_and_serialization():
    compiler = ContractCompiler()
    contract = compiler.compile("Modify only auth.py. Must include OAuth2.")

    prep_resp = ElitePrepareResponse(
        task_id="TASK-123",
        task_contract=contract,
        risk_tier="critical",
        topology_modules=["SecurityGate", "ScopeEnforcer"],
        note="Verified local contract",
    )

    dumped = prep_resp.model_dump()
    assert dumped["schema_version"] == "1.0.0"
    assert dumped["task_id"] == "TASK-123"
    assert len(dumped["task_contract"]["requirements"]) >= 1

    verify_resp = EliteVerifyResponse(
        overall_status=VerificationStatus.PASS,
        passed_count=2,
        failed_count=0,
        unknown_count=0,
        not_checked_count=0,
    )

    assert verify_resp.schema_version == "1.0.0"
    assert verify_resp.overall_status == VerificationStatus.PASS
