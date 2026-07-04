import json

from core.orchestration.capabilities import (
    build_capability_registry,
    format_capability_report,
    parse_jsonc,
    scan_zed_context_servers,
)
from core.tools.orchestration import orchestrate_request


def test_parse_jsonc_supports_zed_comments_and_trailing_commas():
    data = parse_jsonc(
        """
        // Zed settings
        {
          "context_servers": {
            "elite-reasoning": {
              "command": "/tmp/elite-reasoning-mcp",
            },
          },
        }
        """
    )
    assert data["context_servers"]["elite-reasoning"]["command"] == "/tmp/elite-reasoning-mcp"


def test_scan_zed_context_servers_reports_configured_servers(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "context_servers": {
                    "elite-reasoning": {
                        "command": "/Users/test/.local/bin/elite-reasoning-mcp",
                        "args": [],
                    },
                    "disabled-server": {"enabled": False, "command": "noop"},
                }
            }
        )
    )

    caps = scan_zed_context_servers(str(settings))
    by_name = {cap.name: cap for cap in caps}

    assert by_name["elite-reasoning"].status == "configured"
    assert by_name["elite-reasoning"].confidence == 0.85
    assert by_name["disabled-server"].status == "unavailable"


def test_registry_suppresses_cross_ide_skills_when_zed_is_active(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ELITE_ALLOW_CROSS_IDE_SKILLS", raising=False)
    monkeypatch.delenv("ELITE_VISIBLE_SKILLS", raising=False)

    zed_settings = tmp_path / ".config" / "zed" / "settings.json"
    zed_settings.parent.mkdir(parents=True)
    zed_settings.write_text(json.dumps({"context_servers": {"elite-reasoning": {"command": "elite-reasoning-mcp"}}}))

    legacy_skill = tmp_path / ".gemini" / "config" / "plugins" / "research" / "skills" / "arxiv"
    legacy_skill.mkdir(parents=True)

    registry = build_capability_registry(str(zed_settings))

    assert registry.active_ide == "zed"
    assert registry.names("mcp") == ["elite-reasoning"]
    assert "arxiv" not in registry.names("skill")
    assert any("legacy Gemini" in warning for warning in registry.warnings)


def test_env_visible_skills_override_zed_suppression(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ELITE_VISIBLE_SKILLS", "arxiv,research-router")

    zed_settings = tmp_path / ".config" / "zed" / "settings.json"
    zed_settings.parent.mkdir(parents=True)
    zed_settings.write_text(json.dumps({"context_servers": {"elite-reasoning": {"command": "elite-reasoning-mcp"}}}))

    registry = build_capability_registry(str(zed_settings))

    assert registry.active_ide == "zed"
    assert registry.names("skill") == ["arxiv", "research-router"]


def test_capability_report_is_human_readable(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    zed_settings = tmp_path / ".config" / "zed" / "settings.json"
    zed_settings.parent.mkdir(parents=True)
    zed_settings.write_text(json.dumps({"context_servers": {"elite-reasoning": {"command": "elite-reasoning-mcp"}}}))

    report = format_capability_report(build_capability_registry(str(zed_settings)))

    assert "Capability Verification Report" in report
    assert "elite-reasoning" in report
    assert "Active IDE" in report


def test_orchestrator_uses_zed_capabilities_not_legacy_skills(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ELITE_VISIBLE_SKILLS", raising=False)
    monkeypatch.delenv("ELITE_ALLOW_CROSS_IDE_SKILLS", raising=False)

    zed_settings = tmp_path / ".config" / "zed" / "settings.json"
    zed_settings.parent.mkdir(parents=True)
    zed_settings.write_text(json.dumps({"context_servers": {"elite-reasoning": {"command": "elite-reasoning-mcp"}}}))
    legacy_skill = tmp_path / ".gemini" / "config" / "plugins" / "research" / "skills" / "arxiv"
    legacy_skill.mkdir(parents=True)

    plan = orchestrate_request("research the best benchmark for coding agents")

    assert "Active IDE:** `zed`" in plan
    assert "`elite-reasoning`" in plan
    assert "`arxiv`" not in plan
    assert "ROI budget tier:** `research_grade`" in plan
