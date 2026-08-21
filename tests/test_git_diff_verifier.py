from core.contracts.models import Requirement, RequirementKind
from core.verification.models import VerificationStatus
from core.verification.registry import GLOBAL_VERIFIER_REGISTRY


def test_git_diff_scope_verifier():
    req = Requirement(
        id="REQ-DIFF-01",
        kind=RequirementKind.ALLOWED_FILES,
        source_text="modify only core/api.py",
        interpretation="Modify only core/api.py",
        verifier="git_diff_verifier",
        verifier_parameters={"allowed_files": ["core/api.py", "api.py"]},
    )

    # PASS case
    diff_ok = """
diff --git a/core/api.py b/core/api.py
--- a/core/api.py
+++ b/core/api.py
@@ -1,3 +1,4 @@
+ # updated
"""
    res_ok = GLOBAL_VERIFIER_REGISTRY.verify_requirement(req, diff_ok)
    assert res_ok.status == VerificationStatus.PASS

    # FAIL case (modifies unauthorized file)
    diff_bad = """
diff --git a/core/secrets.py b/core/secrets.py
--- a/core/secrets.py
+++ b/core/secrets.py
@@ -1,3 +1,4 @@
+ # leaked
"""
    res_bad = GLOBAL_VERIFIER_REGISTRY.verify_requirement(req, diff_bad)
    assert res_bad.status == VerificationStatus.FAIL
    assert "unauthorized file" in res_bad.reason
