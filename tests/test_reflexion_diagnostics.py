from core.verification.diagnostics import extract_diagnostic_slice


def test_extract_diagnostic_slice():
    sample_traceback = """
Traceback (most recent call last):
  File "auth/service.py", line 42, in verify_token
    user_id = payload["sub"]
KeyError: 'sub'
"""
    source_code = """def verify_token(payload):
    # verify
    user_id = payload["sub"]
    return user_id
"""
    diag = extract_diagnostic_slice(sample_traceback, source_code)

    assert diag.failing_file == "auth/service.py"
    assert diag.failing_line_number == 42
    assert diag.error_type == "KeyError"
    assert "sub" in diag.error_message
    assert "Add boundary guard or .get()" in diag.suggested_invariant_fix
