import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.validate_claims import (
    END_MARKER,
    START_MARKER,
    load_registry,
    render_claims_block,
    validate_readme,
    validate_registry,
)

ROOT = Path(__file__).resolve().parents[1]


def test_public_claims_registry_and_generated_readme_are_current():
    registry = load_registry(ROOT / "claims.yml")
    errors = validate_registry(registry, root=ROOT, now=datetime(2026, 8, 22, tzinfo=timezone.utc))
    assert errors == []

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert validate_readme(registry, readme) == []
    assert readme.count(START_MARKER) == 1
    assert readme.count(END_MARKER) == 1


def test_registry_rejects_missing_artifacts_and_invalid_external_evidence(tmp_path):
    registry = load_registry(ROOT / "claims.yml")
    changed = copy.deepcopy(registry)
    claim = changed["claims"][0]
    claim["status"] = "externally_replicated"
    claim["evidence"]["artifact"] = "missing-report.json"
    claim["evidence"]["artifact_sha256"] = None

    errors = validate_registry(changed, root=tmp_path, now=datetime(2026, 8, 22, tzinfo=timezone.utc))
    assert any("evidence artifact does not exist" in error for error in errors)
    assert any("requires an artifact digest" in error for error in errors)


def test_readme_validation_rejects_stale_generated_content_and_hype():
    registry = load_registry(ROOT / "claims.yml")
    clean = f"before\n{render_claims_block(registry)}\nafter\n"
    assert validate_readme(registry, clean) == []

    stale = clean.replace("seven-case internal fixture pilot", "untracked experiment", 1)
    assert any("generated claims block is stale" in error for error in validate_readme(registry, stale))

    hyped = clean + "\nThis guarantees zero security vulnerabilities.\n"
    assert any("absolute vulnerability claim" in error for error in validate_readme(registry, hyped))


def test_claims_yml_stays_in_standard_library_parseable_yaml_subset():
    # JSON is a subset of YAML 1.2. This keeps release validation dependency-free.
    raw = (ROOT / "claims.yml").read_text(encoding="utf-8")
    parsed = json.loads(raw)
    assert parsed["schema_version"] == "1.0"
