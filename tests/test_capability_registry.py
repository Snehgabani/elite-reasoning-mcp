import json

import pytest

from core.orchestration.capabilities import (
    build_capability_registry,
    format_capability_report,
    parse_jsonc,
    scan_zed_context_servers,
)
from core.tools import orchestration
from core.tools.goal_prompt_polisher import PolishResult


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


def test_gemini_endpoint_requires_https_and_explicit_custom_host_opt_in(monkeypatch):
    monkeypatch.delenv("ELITE_GEMINI_BASE_URL", raising=False)
    monkeypatch.delenv("ELITE_ALLOW_CUSTOM_GEMINI_ENDPOINT", raising=False)
    assert orchestration._gemini_endpoint().startswith("https://generativelanguage.googleapis.com/")

    monkeypatch.setenv("ELITE_GEMINI_BASE_URL", "http://localhost:8080/gemini")
    with pytest.raises(ValueError, match="https"):
        orchestration._gemini_endpoint()

    monkeypatch.setenv("ELITE_GEMINI_BASE_URL", "https://provider.example.test/gemini")
    with pytest.raises(ValueError, match="ELITE_ALLOW_CUSTOM_GEMINI_ENDPOINT"):
        orchestration._gemini_endpoint()

    monkeypatch.setenv("ELITE_ALLOW_CUSTOM_GEMINI_ENDPOINT", "1")
    assert orchestration._gemini_endpoint() == "https://provider.example.test/gemini"


def test_eval_harness_contract_rejects_unknown_values():
    assert "Unsupported eval harness" in orchestration._validated_eval_harness("unknown")
    assert "promptfoo" in orchestration._validated_eval_harness("promptfoo").lower()


def test_orchestrator_records_prompt_polisher_intent(tmp_path, monkeypatch):
    class RecordingStore:
        records = []

        def record_prompt_intent(self, **record):
            self.records.append(record)

    class TestPolisher:
        def __init__(self, store):
            self.store = store

        def polish(self, prompt):
            return PolishResult(
                original_prompt=prompt,
                polished_prompt=prompt,
                original_score=55,
                polished_score=75,
                intent="build",
                complexity=3,
            )

    store = RecordingStore()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ELITE_DIR", str(tmp_path / "profile"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(orchestration, "_polisher", TestPolisher(store))

    orchestration.orchestrate_request("build a safe deploy workflow")

    assert len(store.records) == 1
    assert store.records[0]["intent"] == "build"
    assert store.records[0]["prompt_text"] == "build a safe deploy workflow"


def test_orchestrator_uses_zed_capabilities_not_legacy_skills(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ELITE_VISIBLE_SKILLS", raising=False)
    monkeypatch.delenv("ELITE_ALLOW_CROSS_IDE_SKILLS", raising=False)

    zed_settings = tmp_path / ".config" / "zed" / "settings.json"
    zed_settings.parent.mkdir(parents=True)
    zed_settings.write_text(json.dumps({"context_servers": {"elite-reasoning": {"command": "elite-reasoning-mcp"}}}))
    legacy_skill = tmp_path / ".gemini" / "config" / "plugins" / "research" / "skills" / "arxiv"
    legacy_skill.mkdir(parents=True)

    plan = orchestration.orchestrate_request("research the best benchmark for coding agents")

    assert "Active IDE:** `zed`" in plan
    assert "`elite-reasoning`" in plan
    assert "`arxiv`" not in plan
    assert "ROI budget tier:** `research_grade`" in plan
