#!/usr/bin/env python3
"""Validate the public claims registry and its generated README block.

`claims.yml` intentionally uses JSON syntax, which is valid YAML 1.2. Keeping the
registry in the JSON subset lets release checks validate it with Python's
standard library instead of adding a package dependency solely for release
metadata.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "claims.yml"
DEFAULT_README = ROOT / "README.md"
START_MARKER = "<!-- BEGIN GENERATED CLAIMS -->"
END_MARKER = "<!-- END GENERATED CLAIMS -->"

ALLOWED_STATUSES = frozenset({"internal_pilot", "implementation_verified", "externally_replicated", "retired"})
ALLOWED_REPLICATION = frozenset(
    {"not_independently_replicated", "repository_tests_only", "independently_replicated", "not_applicable"}
)
REQUIRED_CLAIM_FIELDS = frozenset(
    {
        "id",
        "name",
        "statement",
        "scope",
        "exclusions",
        "metric_definition",
        "dataset_version",
        "code_version",
        "run_id",
        "sample_size",
        "result",
        "evidence",
        "replication_status",
        "status",
        "expires_at",
        "owner",
        "permitted_public_wording",
    }
)
FORBIDDEN_PUBLIC_PATTERNS = {
    r"\+1,?480\s+Elo": "unregistered +1,480 Elo claim",
    r"frontier-level task adherence": "unsupported frontier-level claim",
    r"90[–-]95%\s+LLM cost reduction": "unsupported cost-reduction claim",
    r"zero security vulnerabilities": "absolute vulnerability claim",
    r"zero syntax crashes": "absolute syntax-crash claim",
    r">\s*140,?000\s+ops/sec": "unregistered throughput claim",
}


class ClaimsValidationError(ValueError):
    """Raised when public claim metadata is inconsistent or incomplete."""


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ClaimsValidationError(f"cannot read claims registry {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ClaimsValidationError(
            f"{path} must remain in the JSON-compatible subset of YAML: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(data, dict):
        raise ClaimsValidationError("claims registry root must be an object")
    return data


def _parse_timestamp(value: object, field: str, claim_id: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ClaimsValidationError(f"{claim_id}: {field} must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ClaimsValidationError(f"{claim_id}: {field} is not a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ClaimsValidationError(f"{claim_id}: {field} must include a timezone")
    return parsed


def validate_registry(registry: dict[str, Any], *, root: Path = ROOT, now: datetime | None = None) -> list[str]:
    errors: list[str] = []
    now = now or datetime.now(timezone.utc)

    if registry.get("schema_version") != "1.0":
        errors.append("registry schema_version must be '1.0'")
    for field in ("product_version", "updated_at", "owner"):
        if not isinstance(registry.get(field), str) or not registry[field].strip():
            errors.append(f"registry {field} must be a non-empty string")

    claims = registry.get("claims")
    if not isinstance(claims, list) or not claims:
        return errors + ["registry claims must be a non-empty list"]

    seen_ids: set[str] = set()
    for index, claim in enumerate(claims, 1):
        prefix = f"claim #{index}"
        if not isinstance(claim, dict):
            errors.append(f"{prefix} must be an object")
            continue
        claim_id = str(claim.get("id") or prefix)
        missing = sorted(REQUIRED_CLAIM_FIELDS - claim.keys())
        if missing:
            errors.append(f"{claim_id}: missing required fields: {', '.join(missing)}")
        if claim_id in seen_ids:
            errors.append(f"{claim_id}: duplicate claim id")
        seen_ids.add(claim_id)
        if not re.fullmatch(r"CLAIM-\d{3}", claim_id):
            errors.append(f"{claim_id}: id must match CLAIM-NNN")

        status = claim.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{claim_id}: invalid status {status!r}")
        replication = claim.get("replication_status")
        if replication not in ALLOWED_REPLICATION:
            errors.append(f"{claim_id}: invalid replication_status {replication!r}")
        exclusions = claim.get("exclusions")
        if not isinstance(exclusions, list) or not exclusions or not all(isinstance(item, str) for item in exclusions):
            errors.append(f"{claim_id}: exclusions must be a non-empty list of strings")
        wording = claim.get("permitted_public_wording")
        if not isinstance(wording, str) or len(wording.strip()) < 30:
            errors.append(f"{claim_id}: permitted_public_wording must be a substantive string")

        evidence = claim.get("evidence")
        if not isinstance(evidence, dict):
            errors.append(f"{claim_id}: evidence must be an object")
        else:
            artifact = evidence.get("artifact")
            command = evidence.get("command")
            if not isinstance(artifact, str) or not artifact:
                errors.append(f"{claim_id}: evidence.artifact must be a repository-relative path")
            else:
                artifact_path = (root / artifact).resolve()
                try:
                    artifact_path.relative_to(root.resolve())
                except ValueError:
                    errors.append(f"{claim_id}: evidence.artifact escapes repository root")
                else:
                    if not artifact_path.is_file():
                        errors.append(f"{claim_id}: evidence artifact does not exist: {artifact}")
            if not isinstance(command, str) or not command.strip():
                errors.append(f"{claim_id}: evidence.command must be non-empty")
            digest = evidence.get("artifact_sha256")
            if digest is not None and not re.fullmatch(r"[a-f0-9]{64}", str(digest)):
                errors.append(f"{claim_id}: evidence.artifact_sha256 must be null or a lowercase SHA-256 digest")
            if status in {"externally_replicated"} and digest is None:
                errors.append(f"{claim_id}: externally replicated evidence requires an artifact digest")

        try:
            expiry = _parse_timestamp(claim.get("expires_at"), "expires_at", claim_id)
            if status not in {"retired", "internal_pilot"} and expiry < now:
                errors.append(f"{claim_id}: active public claim expired at {claim.get('expires_at')}")
        except ClaimsValidationError as exc:
            errors.append(str(exc))

    return errors


def render_claims_block(registry: dict[str, Any]) -> str:
    lines = [
        START_MARKER,
        "### Current evidence summary",
        "",
        "> Claims below are generated from [`claims.yml`](claims.yml). Implementation checks describe covered behavior; the internal pilot is not evidence of broad model improvement.",
        "",
    ]
    for claim in registry["claims"]:
        status = str(claim["status"]).replace("_", " ")
        lines.extend(
            [
                f"- **{claim['name']}** — {claim['permitted_public_wording']} "
                f"_Status: {status}; replication: {str(claim['replication_status']).replace('_', ' ')}._",
            ]
        )
    lines.extend(["", END_MARKER])
    return "\n".join(lines)


def replace_generated_block(readme: str, block: str) -> str:
    pattern = re.compile(re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), flags=re.DOTALL)
    matches = pattern.findall(readme)
    if len(matches) != 1:
        raise ClaimsValidationError(
            f"README must contain exactly one generated claims block ({START_MARKER} ... {END_MARKER}); found {len(matches)}"
        )
    return pattern.sub(block, readme, count=1)


def validate_readme(registry: dict[str, Any], readme: str) -> list[str]:
    errors: list[str] = []
    try:
        expected = replace_generated_block(readme, render_claims_block(registry))
    except ClaimsValidationError as exc:
        return [str(exc)]
    if expected != readme:
        errors.append("README generated claims block is stale; run `python scripts/validate_claims.py --write`")
    for pattern, description in FORBIDDEN_PUBLIC_PATTERNS.items():
        if re.search(pattern, readme, flags=re.IGNORECASE):
            errors.append(f"README contains {description}")
    return errors


def run(*, registry_path: Path, readme_path: Path, write: bool = False) -> list[str]:
    registry = load_registry(registry_path)
    errors = validate_registry(registry, root=ROOT)
    if errors:
        return errors
    readme = readme_path.read_text(encoding="utf-8")
    if write:
        readme = replace_generated_block(readme, render_claims_block(registry))
        readme_path.write_text(readme, encoding="utf-8")
    return validate_readme(registry, readme)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate claims.yml and the generated README evidence summary")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--readme", type=Path, default=DEFAULT_README)
    parser.add_argument("--write", action="store_true", help="replace the generated README block before validating")
    args = parser.parse_args(argv)

    try:
        errors = run(registry_path=args.registry, readme_path=args.readme, write=args.write)
    except (ClaimsValidationError, OSError) as exc:
        errors = [str(exc)]
    if errors:
        for error in errors:
            print(f"claims validation error: {error}", file=sys.stderr)
        return 1
    print(f"Claims registry valid: {args.registry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
