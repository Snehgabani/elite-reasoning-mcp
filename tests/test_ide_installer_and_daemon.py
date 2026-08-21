import json
import pytest
from pathlib import Path
from core.orchestration.ide_installer import MultiIDEInstaller, IDEConfigTarget
from core.eval.benchmark_daemon import BenchmarkDaemon
from core.eval.launchd_manager import LaunchdManager


def test_ide_installer_targets(tmp_path):
    installer = MultiIDEInstaller(binary_path="/mock/bin/elite-reasoning-mcp")
    installer.home = tmp_path

    targets = installer.get_ide_targets()
    assert len(targets) == 5

    # Test installing to mock targets
    results = installer.install_all()
    assert len(results) == 5

    # Check Claude Desktop config
    claude_cfg = tmp_path / "Library/Application Support/Claude/claude_desktop_config.json"
    assert claude_cfg.exists()
    data = json.loads(claude_cfg.read_text())
    assert "elite-reasoning-mcp" in data["mcpServers"]
    assert data["mcpServers"]["elite-reasoning-mcp"]["command"] == "/mock/bin/elite-reasoning-mcp"

    # Check Zed config
    zed_cfg = tmp_path / ".config/zed/settings.json"
    assert zed_cfg.exists()
    zed_data = json.loads(zed_cfg.read_text())
    assert "elite-reasoning-mcp" in zed_data["context_servers"]


def test_benchmark_daemon_execution(tmp_path):
    daemon = BenchmarkDaemon(output_dir=tmp_path)
    res = daemon.execute_cycle(split="dev")

    assert res["status"] == "completed"
    assert res["verdict"] in ("OPTIMAL_LIFT_CERTIFIED", "DIRECTIONAL_LIFT", "INCONCLUSIVE")
    assert (tmp_path / "history.jsonl").exists()
    assert (tmp_path / "LATEST_BENCHMARK.md").exists()


def test_launchd_manager_plist_generation(tmp_path):
    mgr = LaunchdManager(home=tmp_path)
    plist = mgr.generate_plist_content(interval_seconds=3600)
    assert "com.sovereign.elite-benchmark" in plist
    assert "StartInterval" in plist
    assert "3600" in plist
