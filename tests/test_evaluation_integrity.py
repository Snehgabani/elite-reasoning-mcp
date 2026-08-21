import re
import yaml
from pathlib import Path

from core.eval.rct_runner import DoubleBlindRCTRunner
from core.eval.blind_protocol import BLIND_CASES


def test_no_hardcoded_fake_scores_in_eval_scripts():
    scripts_dir = Path(__file__).parent.parent / "scripts"
    for py_file in scripts_dir.glob("*.py"):
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, 1):
            clean_line = line.strip()
            if clean_line.startswith("#") or clean_line.startswith('"""') or clean_line.startswith("'''"):
                continue
            assert not re.search(r"q_treat\s*=\s*0\.98", clean_line), f"Found hardcoded score in {py_file}:{i}"
            assert not re.search(r"return\s+True,\s*0\.98", clean_line), f"Found hardcoded score in {py_file}:{i}"


def test_claims_registry_integrity():
    claims_path = Path(__file__).parent.parent / "claims.yml"
    assert claims_path.exists(), "claims.yml must exist in repository root"

    data = yaml.safe_load(claims_path.read_text(encoding="utf-8"))
    assert "claims" in data
    assert len(data["claims"]) >= 3

    for claim in data["claims"]:
        assert "id" in claim
        assert "statement" in claim
        assert "scope" in claim
        assert "evidence" in claim
        assert "artifact" in claim["evidence"]
        assert "permitted_public_wording" in claim
        assert "status" in claim


def test_double_blind_randomization_non_trivial():
    runner = DoubleBlindRCTRunner(seed=100)
    swaps = []
    for _ in range(20):
        r = runner.run_trial_case(BLIND_CASES[0])
        swaps.append(r.is_order_swapped)
        runner.rng.randint(0, 100)

    assert True in swaps
    assert False in swaps
