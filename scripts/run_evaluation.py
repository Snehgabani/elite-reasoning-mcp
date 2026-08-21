"""Manifest-driven contract extraction evaluation.

This runner measures only what the manifest can objectively score. It does not
simulate host-model arms or manufacture verification accuracy.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from core.contracts.compiler import ContractCompiler


def _tokens(value: object) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9_./-]+", str(value)) if token}


def _matches(expected: dict[str, Any], actual) -> bool:
    if actual.kind.value != expected.get("kind"):
        return False
    parameters = actual.verifier_parameters
    if "term" in expected:
        expected_tokens = _tokens(expected["term"])
        actual_tokens = _tokens(parameters.get("required_terms") or parameters.get("forbidden_terms") or [])
        return bool(expected_tokens & actual_tokens)
    if "files" in expected:
        return set(expected["files"]) == set(parameters.get("allowed_files") or [])
    if "command" in expected:
        return str(expected["command"]).lower() in str(parameters.get("command") or "").lower()
    return True


def run_evaluation_manifest(manifest_path: Path) -> Dict[str, Any]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    tasks = data.get("tasks", [])
    compiler = ContractCompiler()
    expected_count = 0
    matched_count = 0
    extracted_count = 0
    invented_count = 0
    cases: list[dict[str, Any]] = []

    for task in tasks:
        contract = compiler.compile(task["instruction"])
        expected = list(task.get("expected_requirements") or [])
        actual = list(contract.requirements)
        expected_matches = [any(_matches(item, candidate) for candidate in actual) for item in expected]
        actual_matches = [any(_matches(item, candidate) for item in expected) for candidate in actual]
        expected_count += len(expected)
        matched_count += sum(expected_matches)
        extracted_count += len(actual)
        invented_count += sum(not matched for matched in actual_matches)
        cases.append(
            {
                "task_id": task.get("id"),
                "expected": len(expected),
                "extracted": len(actual),
                "matched_expected": sum(expected_matches),
                "invented": sum(not matched for matched in actual_matches),
            }
        )

    recall = matched_count / expected_count if expected_count else 0.0
    invented_rate = invented_count / extracted_count if extracted_count else 0.0
    return {
        "schema_version": "1.1.0",
        "manifest_version": data.get("schema_version", "unknown"),
        "dataset_version": data.get("dataset_version", "unknown"),
        "total_tasks": len(tasks),
        "compiled_contracts": sum(1 for case in cases if case["extracted"] > 0),
        "expected_requirement_count": expected_count,
        "extracted_requirement_count": extracted_count,
        "matched_requirement_count": matched_count,
        "exact_requirement_recall": round(recall, 4),
        "critical_invented_rate": round(invented_rate, 4),
        "verification_accuracy": None,
        "cases": cases,
        "limitations": [
            "This measures deterministic contract extraction only.",
            "No host model candidates were generated or evaluated.",
            "The two-task manifest is a development smoke set, not confirmatory evidence.",
        ],
    }


def main() -> None:
    manifest_path = Path(__file__).resolve().parent.parent / "evals/manifests/eval_manifest_v1.json"
    print(json.dumps(run_evaluation_manifest(manifest_path), indent=2))


if __name__ == "__main__":
    main()
