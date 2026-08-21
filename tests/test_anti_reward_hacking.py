from core.verification.git_diff import check_test_tampering


def test_check_test_tampering_blocks_unauthorized_test_edits():
    # Bug fix task modifying application code only -> Allowed
    ok, msg = check_test_tampering(["core/auth.py", "core/utils.py"], task_type="bug_fix")
    assert ok is True
    assert msg == ""

    # Bug fix task modifying tests directory -> Blocked
    ok, msg = check_test_tampering(["core/auth.py", "tests/test_auth.py"], task_type="bug_fix")
    assert ok is False
    assert "REWARD_HACKING_DETECTED" in msg
    assert "tests/test_auth.py" in msg

    # Explicitly authorized test edits -> Allowed
    ok, msg = check_test_tampering(["tests/test_auth.py"], task_type="bug_fix", allow_test_edits=True)
    assert ok is True
