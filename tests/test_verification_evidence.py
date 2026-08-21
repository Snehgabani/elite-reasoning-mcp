from core.verification.models import VerificationStatus, evidence_record, status_from_bool, subject_digest


def test_subject_digest_is_typed_deterministic_and_content_sensitive():
    first = subject_digest("draft", "same content")
    repeated = subject_digest("draft", "same content")
    changed_content = subject_digest("draft", "different content")
    changed_kind = subject_digest("code", "same content")

    assert first == repeated
    assert first.startswith("sha256:")
    assert first != changed_content
    assert first != changed_kind


def test_evidence_id_binds_producer_subject_and_payload_but_not_timestamp():
    digest = subject_digest("code", "print('ok')")
    args = {
        "kind": "syntax",
        "producer": "syntax.verify",
        "subject_digest_value": digest,
        "payload": {"passed": True, "issues": []},
        "limitations": ["syntax only"],
    }
    first = evidence_record(**args)
    repeated = evidence_record(**args)
    changed = evidence_record(**{**args, "payload": {"passed": False, "issues": ["bad"]}})

    assert first.id == repeated.id
    assert first.artifact_digest == repeated.artifact_digest
    assert first.collected_at
    assert first.subject_digest == digest
    assert changed.id != first.id


def test_boolean_status_conversion_does_not_conflate_unknown_states():
    assert status_from_bool(True) is VerificationStatus.PASS
    assert status_from_bool(False) is VerificationStatus.FAIL
    assert VerificationStatus.UNKNOWN.value == "UNKNOWN"
    assert VerificationStatus.NOT_CHECKED.value == "NOT_CHECKED"
