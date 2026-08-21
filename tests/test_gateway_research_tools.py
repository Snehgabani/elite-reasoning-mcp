import pytest
from core.integration.mcp_server import create_mcp_server
from core.verification.models import VerificationStatus
from core.verification.registry import GLOBAL_VERIFIER_REGISTRY


@pytest.mark.asyncio
async def test_gateway_elite_verify_cegis_and_diagnostics(tmp_path):
    server = create_mcp_server(brain_dir=str(tmp_path / "brain"), tool_profile="core")
    verify_fn = server._tool_manager._tools["elite_verify"].fn

    # 1. Test CEGIS property check
    unsafe_code = "def get(items): return items[0]"
    res_cegis_unsafe = await verify_fn(check="cegis", code=unsafe_code)
    assert res_cegis_unsafe.check == "cegis"
    assert res_cegis_unsafe.data["status"] == VerificationStatus.FAIL.value

    safe_code = "def get(items):\n    if not items: return None\n    return items[0]"
    res_cegis_safe = await verify_fn(check="cegis", code=safe_code)
    assert res_cegis_safe.data["status"] == VerificationStatus.PASS.value

    # 2. Test Diagnostics check
    tb = 'Traceback (most recent call last):\n  File "foo.py", line 12, in bar\nKeyError: "token"'
    res_diag = await verify_fn(check="diagnostics", query=tb)
    assert res_diag.check == "diagnostics"
    assert res_diag.data["error_type"] == "KeyError"
    assert res_diag.data["failing_line_number"] == 12

    # 3. Test Types check
    untyped = "def calculate(a: int): return a * 2"
    res_types_untyped = await verify_fn(check="types", code=untyped)
    assert res_types_untyped.data["status"] == VerificationStatus.FAIL.value

    typed = "def calculate(a: int) -> int: return a * 2"
    res_types_typed = await verify_fn(check="types", code=typed)
    assert res_types_typed.data["status"] == VerificationStatus.PASS.value


def test_registry_builtins_contains_cegis_and_type():
    reg = GLOBAL_VERIFIER_REGISTRY
    assert reg.get("cegis_property_verifier") is not None
    assert reg.get("type_invariant_verifier") is not None
