from core.integration.demo import run_deterministic_demo


def test_cli_demo_runs_and_passes():
    exit_code = run_deterministic_demo(as_json=True)
    assert exit_code == 0
