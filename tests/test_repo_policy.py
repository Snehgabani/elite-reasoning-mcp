import yaml
from core.contracts.compiler import ContractCompiler
from core.contracts.models import RequirementKind
from core.policy.repo_policy import RepoPolicy


def test_repo_policy_enforcement(tmp_path):
    policy_file = tmp_path / ".elite-policy.yml"
    policy_data = {
        "policy_name": "backend_security_policy",
        "forbidden_terms": ["eval", "exec", "insecure_transport"],
        "required_test_command": "pytest",
        "max_repair_attempts": 1,
    }
    with open(policy_file, "w") as f:
        yaml.dump(policy_data, f)

    policy = RepoPolicy.load_from_file(policy_file)
    assert policy.policy_name == "backend_security_policy"

    compiler = ContractCompiler()
    contract = compiler.compile("Refactor auth logic. Modify only auth.py.")

    # Apply repo policy
    enforced_contract = policy.apply_to_contract(contract)

    # Check that repo-level forbidden terms were injected
    terms_in_contract = [r.verifier_parameters.get("forbidden_terms", []) for r in enforced_contract.requirements]
    flat_terms = [t for sub in terms_in_contract for t in sub]
    assert "eval" in flat_terms
    assert "exec" in flat_terms

    # Check that required test command was injected
    has_test_cmd = any(r.kind == RequirementKind.TEST_COMMAND for r in enforced_contract.requirements)
    assert has_test_cmd is True
    assert enforced_contract.max_repair_attempts == 1
