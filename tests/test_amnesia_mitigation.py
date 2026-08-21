"""
Unit and integration tests for TrajectoryGuardian and Anti-Amnesia step-locking.
"""

from __future__ import annotations

from core.cognitive.trajectory_guardian import (
    TrajectoryGuardian,
    TrajectoryStage,
)
from core.eval.amnesia_benchmark import run_amnesia_simulation_suite, AmnesiaBenchmarkReport


def test_trajectory_guardian_amnesia_detection_and_blocking():
    guardian = TrajectoryGuardian()
    sid = "test_amnesia_session"

    # Step 1: Pre-edit contract
    token = guardian.record_pre_edit_contract(sid, "Implement new Stripe endpoint")
    assert token.stage == TrajectoryStage.CONTRACT_COMPILED
    assert "GATE-CONTRACT" in token.token

    # Step 2: Agent edits 2 files without verifying
    guardian.record_file_edit(sid, "payment.py")
    guardian.record_file_edit(sid, "routes.py")

    state = guardian.get_or_create_session(sid)
    assert state.actions_since_last_verify == 2
    assert state.amnesia_detected is True

    # Step 3: Agent tries to conclude early -> Must be blocked
    ok, reason = guardian.validate_completion_attestation(sid)
    assert ok is False
    assert "AMNESIA DECAY DETECTED" in reason

    # Step 4: Agent heeds the step lock and runs syntax verification
    mid_token = guardian.record_verification_check(sid, "syntax", passed=True)
    assert mid_token is not None
    assert "GATE-MIDVERIFY" in mid_token.token
    assert state.amnesia_detected is False

    # Step 5: Agent runs test verification
    test_token = guardian.record_verification_check(sid, "tests", passed=True)
    assert test_token is not None
    assert "GATE-TESTVERIFY" in test_token.token

    # Step 6: Agent now successfully concludes
    ok_final, msg_final = guardian.validate_completion_attestation(sid)
    assert ok_final is True
    assert "verified successfully" in msg_final


def test_amnesia_benchmark_simulation_suite():
    report = run_amnesia_simulation_suite()
    assert isinstance(report, AmnesiaBenchmarkReport)
    assert report.total_fixtures == 3
    assert report.omission_attempts == 1
    assert report.omissions_detected == 1
    assert report.compliant_completions == 2
    assert report.protocol_fixture_only is True
    assert any("cannot detect host actions" in item for item in report.limitations)
