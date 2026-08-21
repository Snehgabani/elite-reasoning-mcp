import tempfile
from pathlib import Path
from core.verification.git_diff import compute_file_digest, verify_file_snapshot_lock


def test_counter_edit_digest_lock():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "auth.py"
        target.write_text("def auth(): return True\n", encoding="utf-8")
        
        # Agent reads initial state and computes snapshot lock
        expected_digest = compute_file_digest(target)
        assert expected_digest.startswith("sha256:")
        
        # Lock check passes when file is unchanged
        ok, msg = verify_file_snapshot_lock(target, expected_digest)
        assert ok is True
        assert msg == ""
        
        # Human developer makes a counter-edit in IDE
        target.write_text("def auth():\n    # human comment\n    return True\n", encoding="utf-8")
        
        # Lock check fails with STALE_SNAPSHOT_CONFLICT
        ok, msg = verify_file_snapshot_lock(target, expected_digest)
        assert ok is False
        assert "STALE_SNAPSHOT_CONFLICT" in msg
        assert "modified externally" in msg
