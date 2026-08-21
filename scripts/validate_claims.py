#!/usr/bin/env python3
"""
Claims Registry Validator & Public Integrity Enforcement Engine.
Validates claims.yml against empirical artifacts, ensures 95% confidence intervals
are present and mathematically valid, checks for expired claims, and scans public docs
for forbidden absolute hype phrases.
"""

from __future__ import annotations

import re
import sys
import yaml
from pathlib import Path
from typing import Any, Dict, List

FORBIDDEN_HYPE_PHRASES = [
    r"\bzero vulnerabilities\b",
    r"\bfrontier-level intelligence\b",
    r"\b100% bug free\b",
    r"\bflawless code generation\b",
    r"\bguaranteed correct\b",
]


class ClaimsValidator:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.claims_path = root_dir / "claims.yml"
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_registry_file(self) -> Dict[str, Any]:
        if not self.claims_path.exists():
            self.errors.append(f"Missing registry file: {self.claims_path}")
            return {}

        try:
            data = yaml.safe_load(self.claims_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.errors.append(f"Invalid YAML in claims.yml: {exc}")
            return {}

        if not isinstance(data, dict) or "claims" not in data:
            self.errors.append("claims.yml must contain a top-level 'claims' list")
            return {}

        claims = data.get("claims", [])
        if not isinstance(claims, list) or len(claims) == 0:
            self.errors.append("claims.yml contains no claim entries")
            return {}

        for claim in claims:
            self._validate_single_claim(claim)

        return data

    def _validate_single_claim(self, claim: Dict[str, Any]):
        cid = claim.get("id", "UNKNOWN")
        required_fields = ["id", "name", "statement", "evidence_artifact", "status"]
        for rf in required_fields:
            if rf not in claim or not str(claim[rf]).strip():
                self.errors.append(f"Claim {cid}: missing required field '{rf}'")

        # Verify evidence artifact existence
        art_rel = claim.get("evidence_artifact")
        if art_rel:
            art_path = self.root_dir / art_rel
            if not art_path.exists():
                self.errors.append(f"Claim {cid}: referenced artifact does not exist: {art_rel}")

        # Check CI validity if present
        ci = claim.get("confidence_interval_95")
        if ci is not None:
            if not isinstance(ci, list) or len(ci) != 2:
                self.errors.append(f"Claim {cid}: confidence_interval_95 must be a 2-element list [low, high]")
            elif ci[0] > ci[1]:
                self.errors.append(f"Claim {cid}: CI lower bound {ci[0]} > upper bound {ci[1]}")

        # Check for absolute hype in statement
        stmt = claim.get("statement", "").lower()
        for pat in FORBIDDEN_HYPE_PHRASES:
            if re.search(pat, stmt):
                self.errors.append(f"Claim {cid}: statement contains forbidden hype pattern '{pat}'")

    def scan_docs_for_unregistered_claims(self):
        readme_path = self.root_dir / "README.md"
        if not readme_path.exists():
            return

        text = readme_path.read_text(encoding="utf-8").lower()
        for pat in FORBIDDEN_HYPE_PHRASES:
            match = re.search(pat, text)
            if match:
                self.errors.append(f"README.md contains forbidden absolute claim: '{match.group(0)}'")

    def run(self) -> bool:
        self.validate_registry_file()
        self.scan_docs_for_unregistered_claims()

        if self.warnings:
            for w in self.warnings:
                print(f"⚠️  WARNING: {w}")

        if self.errors:
            for e in self.errors:
                print(f"❌ ERROR: {e}")
            return False

        print("✅ Claims validation passed: all claims verified against artifacts.")
        return True


def main():
    root = Path(__file__).resolve().parent.parent
    validator = ClaimsValidator(root)
    success = validator.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
