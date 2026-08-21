from core.contracts.models import Requirement, RequirementKind
from core.plugins.protocol import PluginMetadata, PluginVerifier
from core.verification.models import VerificationResult, VerificationStatus
from core.verification.registry import VerifierRegistry


class CustomJsonVerifier(PluginVerifier):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="custom_json_verifier",
            version="1.0.0",
            author="design_partner",
            description="Checks JSON payload validity",
            supported_kinds=[RequirementKind.OUTPUT_FORMAT],
        )

    def verify(self, requirement, subject_content, evidence_records=None):
        import json

        try:
            json.loads(subject_content)
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.PASS,
                reason="Valid JSON payload",
            )
        except Exception as exc:
            return VerificationResult(
                requirement_id=requirement.id,
                verifier=self.name,
                status=VerificationStatus.FAIL,
                reason=f"Invalid JSON: {exc}",
            )


def test_plugin_verifier_registration_and_execution():
    reg = VerifierRegistry(register_builtins=False)
    verifier = CustomJsonVerifier()
    reg.register(verifier)

    assert reg.get("custom_json_verifier") is not None
    req = Requirement(
        id="REQ-J1",
        kind=RequirementKind.OUTPUT_FORMAT,
        source_text="must be json",
        interpretation="Must be JSON",
        verifier="custom_json_verifier",
    )

    res_ok = reg.verify_requirement(req, '{"status": "ok"}')
    assert res_ok.status == VerificationStatus.PASS

    res_bad = reg.verify_requirement(req, "invalid json")
    assert res_bad.status == VerificationStatus.FAIL
