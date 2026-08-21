from core.verification.models import Evidence, VerificationResult, VerificationStatus


def test_evidence_digest_computation_and_binding():
    code = "def authenticate(): return True"
    digest = Evidence.compute_subject_digest(code)

    ev = Evidence(
        id="EV-AST-01",
        kind="ast_parse",
        producer="python_ast_verifier",
        subject_digest=digest,
        payload={"valid_syntax": True},
    )

    assert len(ev.subject_digest) == 64
    assert ev.subject_digest == Evidence.compute_subject_digest(code)

    res = VerificationResult(
        requirement_id="REQ-SYNTAX-01",
        verifier="ast_syntax_verifier",
        status=VerificationStatus.PASS,
        reason="Python AST parsed with 0 syntax errors",
        evidence_ids=[ev.id],
        duration_ms=1.2,
    )

    assert res.status == VerificationStatus.PASS
    assert len(res.evidence_ids) == 1
