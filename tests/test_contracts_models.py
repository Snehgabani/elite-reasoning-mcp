from core.contracts.models import (
    Requirement,
    RequirementKind,
    RequirementSeverity,
    RequirementStatus,
    RiskTier,
    TaskContract,
    EvidenceRequirement,
)


def test_task_contract_serialization():
    req = Requirement(
        id="REQ-001",
        kind=RequirementKind.REQUIRED_CONTENT,
        source_text="must include test",
        source_start=10,
        source_end=27,
        interpretation="Contains exact substring 'test'",
        severity=RequirementSeverity.CRITICAL,
        verifier="constraint_verifier",
        verifier_parameters={"terms": ["test"]},
        extraction_confidence=0.95,
        status=RequirementStatus.CONFIRMED,
    )

    contract = TaskContract(
        schema_version="1.0.0",
        goal="Run full verification",
        deliverable="Passing test suite",
        requirements=[req],
        non_goals=["No mock replacements"],
        evidence_requirements=[EvidenceRequirement(id="EV-1", kind="test_log", required_for_requirements=["REQ-001"])],
        risk_tier=RiskTier.STANDARD,
        stop_conditions=["All tests pass"],
        max_repair_attempts=2,
    )

    data = contract.model_dump()
    assert data["schema_version"] == "1.0.0"
    assert len(data["requirements"]) == 1
    assert data["requirements"][0]["id"] == "REQ-001"
    assert data["requirements"][0]["severity"] == "critical"

    rebuilt = TaskContract.model_validate(data)
    assert rebuilt.requirements[0].kind == RequirementKind.REQUIRED_CONTENT
