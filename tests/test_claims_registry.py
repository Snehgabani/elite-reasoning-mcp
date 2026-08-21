from pathlib import Path
from scripts.validate_claims import ClaimsValidator


def test_claims_registry_validation_passes():
    root = Path(__file__).resolve().parent.parent
    validator = ClaimsValidator(root)
    assert validator.run() is True
    assert len(validator.errors) == 0


def test_claims_validator_rejects_missing_file(tmp_path):
    validator = ClaimsValidator(tmp_path)
    assert validator.run() is False
    assert any("Missing registry file" in e for e in validator.errors)
