import sys
import pytest

sys.path.insert(0, ".")
from core.cognitive.engine import _COGNITIVE_ENGINE
from core.cognitive.leverage.deterministic_gates import (
    validate_security_invariants,
    validate_syntax,
)
from core.cognitive.leverage.prm_verifier import ProcessRewardModel
from core.integration.mcp_server import create_mcp_server


def test_prm_verification_math():
    prm = ProcessRewardModel()
    res = prm.verify_step_sync("Let y = 10 / 0")
    assert res["passed"] is False
    assert any("division by zero" in issue.lower() for issue in res["issues"])

def test_deterministic_gates_ast_python():
    valid_code = "def add(a, b):\n    return a + b\n"
    res = validate_syntax(valid_code, "python")
    assert res.passed is True
    assert res.score == 1.0

    invalid_code = "def broken_syntax(a, b:\n    return a + b"
    res2 = validate_syntax(invalid_code, "python")
    assert res2.passed is False

def test_deterministic_gates_security_owasp():
    bad_code = "import os\nos.system(\"rm -rf /\")\n"
    res = validate_security_invariants(bad_code)
    assert res.passed is False
    assert any("Fatal Security Violation" in issue for issue in res.issues)

@pytest.mark.asyncio
async def test_execute_mix_pipeline():
    res = await _COGNITIVE_ENGINE.execute_mix("Build an immutable distributed event ledger")
    assert res["status"] == "SUCCESS"
    assert len(res["proof_of_work"]["verification_hash"]) == 64
    assert len(res["layers_executed"]) == 9
    assert res["prm_passed"] is True

def test_unified_mcp_server_registration():
    server = create_mcp_server("/tmp/test_brain_pytest", tool_profile="legacy")
    tools = [t.name for t in server._tool_manager.list_tools()]
    assert "execute_mix" in tools
    assert "elite_reason" in tools
    assert "prm_verify_step" in tools
    assert "repo_search" in tools
    assert "apply_reasoning_diff" in tools
    assert "god_tier_reasoning" in tools
