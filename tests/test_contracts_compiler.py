from core.contracts.compiler import ContractCompiler
from core.contracts.models import RequirementKind, RequirementSeverity, RiskTier


def test_contract_compiler_source_spans():
    compiler = ContractCompiler()
    prompt = "Refactor user authentication. Must include OAuth2 and do not use bcrypt. Run pytest."
    contract = compiler.compile(prompt)

    assert contract.schema_version == "1.0.0"
    assert len(contract.requirements) == 3
    assert contract.risk_tier == RiskTier.CRITICAL

    # 1. Check required content requirement
    req_content = next(r for r in contract.requirements if r.kind == RequirementKind.REQUIRED_CONTENT)
    assert req_content.severity == RequirementSeverity.CRITICAL
    assert "OAuth2" in req_content.verifier_parameters["required_terms"]
    # Check span matches verbatim text in prompt
    assert prompt[req_content.source_start : req_content.source_end] == req_content.source_text

    # 2. Check forbidden requirement
    req_forbid = next(r for r in contract.requirements if r.kind == RequirementKind.FORBIDDEN_CONTENT)
    assert "bcrypt" in req_forbid.verifier_parameters["forbidden_terms"]
    assert prompt[req_forbid.source_start : req_forbid.source_end] == req_forbid.source_text

    # 3. Check test requirement
    req_test = next(r for r in contract.requirements if r.kind == RequirementKind.TEST_COMMAND)
    assert prompt[req_test.source_start : req_test.source_end] == req_test.source_text
