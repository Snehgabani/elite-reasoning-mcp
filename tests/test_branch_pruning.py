from core.contracts.compiler import ContractCompiler
from core.search.branch_pruner import prune_candidate_branches


def test_candidate_branch_pruning():
    compiler = ContractCompiler()
    contract = compiler.compile("Refactor auth. Must include OAuth2 and avoid md5. Modify only auth.py.")

    candidates = [
        "def login():\n    # Using md5\n    return 'bad'",  # Fails forbidden md5
        "def login():\n    # Basic login\n    return 'ok'",  # Fails missing OAuth2
        "def login():\n    # Using OAuth2\n    return 'token'",  # Passes all!
    ]

    result = prune_candidate_branches(contract, candidates)

    assert result.total_candidates == 3
    assert result.pruned_candidates == 2
    assert result.surviving_candidates == 1
    assert result.champion_branch is not None
    assert "OAuth2" in result.champion_branch.candidate_code
    assert result.champion_branch.is_pruned is False
