"""
Unit tests for Anti-Falsification and Cryptographic Authenticity Attestation.
"""

from __future__ import annotations

import ast
from core.cognitive.leverage.anti_falsification import (
    AntiFalsificationScanner,
    CodebaseAuthenticityAuditor,
)


def test_anti_falsification_scanner_detects_vacuous_assertions():
    bad_code = """
def test_something():
    assert True
    assert 1 == 1
    x = 42
    assert x == 42
"""
    scanner = AntiFalsificationScanner("test_bad.py", bad_code)
    tree = ast.parse(bad_code)
    scanner.visit(tree)

    anomalies = [a.anomaly_type for a in scanner.anomalies]
    assert "VACUOUS_ASSERTION" in anomalies
    assert len([a for a in scanner.anomalies if a.anomaly_type == "VACUOUS_ASSERTION"]) == 2


def test_anti_falsification_scanner_detects_empty_stub_logic():
    bad_code = """
def production_critical_function():
    pass
"""
    scanner = AntiFalsificationScanner("core/test_dummy.py", bad_code)
    tree = ast.parse(bad_code)
    scanner.visit(tree)

    anomalies = [a.anomaly_type for a in scanner.anomalies]
    assert "EMPTY_STUB_LOGIC" in anomalies


def test_codebase_authenticity_auditor_runs_cleanly():
    auditor = CodebaseAuthenticityAuditor()
    report = auditor.audit_codebase(["core"])

    assert report.total_files_scanned > 20
    assert report.total_ast_nodes_audited > 1000
    assert len(report.cryptographic_codebase_hash) == 64
    assert report.is_genuine is True


def test_attest_execution_authenticity_generates_hmac():
    auditor = CodebaseAuthenticityAuditor()
    attestation = auditor.attest_execution(
        task_id="AUDIT-TEST-01",
        input_payload={"query": "SELECT count(*) FROM table;"},
        output_payload={"count": 100},
    )

    assert attestation["task_id"] == "AUDIT-TEST-01"
    assert len(attestation["proof_hmac"]) == 64
    assert len(attestation["codebase_ast_hash"]) == 64
    assert attestation["is_genuine"] is True
