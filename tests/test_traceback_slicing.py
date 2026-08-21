from core.verification.diagnostics import extract_diagnostic_slice, slice_raw_traceback


def test_traceback_slicing_prunes_boilerplate_and_bounds_length():
    # Construct a huge 1,000-line simulated framework traceback
    lines = ["Traceback (most recent call last):"]
    for i in range(1000):
        lines.append(
            f'  File "/Users/user/project/.venv/lib/python3.13/site-packages/pytest/runner.py", line {i}, in runtest'
        )
        lines.append("    item.runtest()")
    lines.append('  File "/Users/user/project/core/auth.py", line 42, in login')
    lines.append("    user = db[username]")
    lines.append("KeyError: 'admin'")

    raw_trace = "\n".join(lines)
    assert len(raw_trace) > 50000

    sliced = slice_raw_traceback(raw_trace, max_frames=3, max_chars=1500)
    assert len(sliced) <= 1500
    assert "site-packages/pytest" not in sliced
    assert "KeyError: 'admin'" in sliced

    diagnostic = extract_diagnostic_slice(raw_trace)
    assert diagnostic.failing_file == "/Users/user/project/core/auth.py"
    assert diagnostic.failing_line_number == 42
    assert diagnostic.error_type == "KeyError"
    assert "admin" in diagnostic.error_message
