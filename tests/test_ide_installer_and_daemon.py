import json
import stat

import pytest

from core.eval.benchmark_daemon import BenchmarkDaemon
from core.eval.launchd_manager import LaunchdManager
from core.orchestration.ide_installer import IDEConfigError, MultiIDEInstaller


def test_ide_installer_targets_and_valid_core_command(tmp_path):
    installer = MultiIDEInstaller(binary_path="/mock/bin/elite-reasoning-mcp")
    installer.home = tmp_path

    targets = installer.get_ide_targets()
    assert len(targets) == 5
    results = installer.install_all()
    assert len(results) == 5

    claude_cfg = tmp_path / "Library/Application Support/Claude/claude_desktop_config.json"
    data = json.loads(claude_cfg.read_text())
    entry = data["mcpServers"]["elite-reasoning"]
    assert entry["command"] == "/mock/bin/elite-reasoning-mcp"
    assert entry["args"] == []
    assert entry["env"]["ELITE_TOOL_PROFILE"] == "core"
    assert stat.S_IMODE(claude_cfg.stat().st_mode) == 0o600

    zed_cfg = tmp_path / ".config/zed/settings.json"
    zed_data = json.loads(zed_cfg.read_text())
    assert zed_data["context_servers"]["elite-reasoning"]["command"]["args"] == []


def test_ide_installer_preview_is_non_destructive_and_preserves_existing_config(tmp_path):
    installer = MultiIDEInstaller(binary_path="/mock/bin/elite-reasoning-mcp")
    installer.home = tmp_path
    target = installer.target_for("cursor")
    target.config_path.parent.mkdir(parents=True)
    target.config_path.write_text('{"existing": {"keep": true}}', encoding="utf-8")

    preview = installer.preview_target(target)
    assert preview["status"] == "preview"
    assert preview["config"]["existing"] == {"keep": True}
    assert json.loads(target.config_path.read_text()) == {"existing": {"keep": True}}

    installer.install_to_target(target)
    installed = json.loads(target.config_path.read_text())
    assert installed["existing"] == {"keep": True}
    assert "elite-reasoning" in installed["mcpServers"]


def test_ide_installer_refuses_to_overwrite_malformed_json(tmp_path):
    installer = MultiIDEInstaller(binary_path="/mock/bin/elite-reasoning-mcp")
    installer.home = tmp_path
    target = installer.target_for("cursor")
    target.config_path.parent.mkdir(parents=True)
    target.config_path.write_text("{broken", encoding="utf-8")

    with pytest.raises(IDEConfigError, match="refusing to overwrite"):
        installer.install_to_target(target)
    assert target.config_path.read_text() == "{broken"


def test_benchmark_daemon_execution(tmp_path):
    daemon = BenchmarkDaemon(output_dir=tmp_path)
    res = daemon.execute_cycle(split="dev")

    assert res["status"] == "completed"
    assert res["verdict"] in ("PRIMARY_ENDPOINT_SIGNIFICANT", "INTERNAL_PILOT_DIRECTIONAL", "INCONCLUSIVE")
    assert (tmp_path / "history.jsonl").exists()
    assert (tmp_path / "LATEST_BENCHMARK.md").exists()


def test_launchd_manager_plist_generation(tmp_path):
    mgr = LaunchdManager(home=tmp_path)
    plist = mgr.generate_plist_content(interval_seconds=3600)
    assert "com.sovereign.elite-benchmark" in plist
    assert "StartInterval" in plist
    assert "3600" in plist
