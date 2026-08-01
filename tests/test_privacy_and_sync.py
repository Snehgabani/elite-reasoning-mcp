import json
import os
import sqlite3
import stat
from pathlib import Path

import pytest

from core.identity.user_profile import UserProfile
from core.integration.mcp_server import create_mcp_server
from core.memory.persistent_store import EliteStore
from core.middleware.base import CallContext, CallResult
from core.middleware.telemetry import UsageLogMiddleware
from core.privacy import prompt_storage_value, redact_text, telemetry_summary
from core.sync_security import authorize_manual_sync, validate_sync_endpoint


def test_default_telemetry_and_workflow_storage_withhold_raw_prompt(monkeypatch, tmp_path):
    secret = "sk-12345678901234567890"
    monkeypatch.delenv("ELITE_ALLOW_RAW_PROMPT_STORAGE", raising=False)
    monkeypatch.delenv("ELITE_TELEMETRY_MODE", raising=False)

    assert secret not in telemetry_summary({"api_key": secret})
    stored_prompt = prompt_storage_value(f"ship with api_key={secret}")
    assert stored_prompt.startswith("[prompt withheld; sha256:")
    assert secret not in stored_prompt

    store = EliteStore(str(tmp_path / "brain"))
    store.record_workflow_run(
        {
            "run_id": "workflow-private",
            "user_prompt": f"ship with api_key={secret}",
            "intent": "build",
        },
        [],
    )
    workflow = store.get_workflow_run("workflow-private")
    assert workflow is not None
    assert secret not in workflow["user_prompt"]
    assert workflow["user_prompt"].startswith("[prompt withheld;")


def test_explicit_raw_prompt_storage_still_redacts_secrets(monkeypatch):
    secret = "sk-12345678901234567890"
    monkeypatch.setenv("ELITE_ALLOW_RAW_PROMPT_STORAGE", "1")
    monkeypatch.setenv("ELITE_TELEMETRY_MODE", "summary")

    stored_prompt = prompt_storage_value(f'{{"api_key": "{secret}"}}')
    summary = telemetry_summary({"api_key": secret})

    assert secret not in stored_prompt
    assert "[REDACTED]" in stored_prompt
    assert secret not in summary
    assert "[REDACTED]" in summary


def test_bearer_credentials_are_redacted_before_any_key_value_processing(tmp_path):
    token = "example-token"
    rendered = redact_text(f"Authorization: Bearer {token}", limit=5000)

    assert token not in rendered
    assert "[REDACTED]" in rendered

    store = EliteStore(str(tmp_path / "brain"))
    item_id = store.record_memory_item("credential", f"Authorization: Bearer {token}")
    with sqlite3.connect(store.db_path) as conn:
        persisted = conn.execute("SELECT content FROM memory_items WHERE id = ?", (item_id,)).fetchone()[0]
    assert token not in persisted


def test_profile_migration_removes_secrets_and_disables_boot_sync(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "user_id": "test-user",
                "ide_type": "cursor",
                "sync": {
                    "enabled": True,
                    "api_key": "persisted-sync-secret",
                    "auto_sync_on_boot": True,
                },
                "orchestration": {"gemini_api_key": "persisted-provider-secret"},
            }
        ),
        encoding="utf-8",
    )

    profile = UserProfile(str(tmp_path))
    config = profile.config

    assert "api_key" not in config["sync"]
    assert config["sync"]["auto_sync_on_boot"] is False
    assert "gemini_api_key" not in config["orchestration"]
    assert config["ide_type"] == "auto"
    assert config["ide_type_source"] == "auto"
    assert config["user_id"] == "local-user"
    assert config["display_name"] == "Local User"
    assert config["identity_mode"] == "anonymous"
    assert stat.S_IMODE(os.stat(config_path).st_mode) == 0o600


def test_profile_uses_anonymous_identity_and_hides_local_metadata(tmp_path, monkeypatch):
    monkeypatch.delenv("ELITE_USER_ID", raising=False)
    monkeypatch.delenv("ELITE_DISPLAY_NAME", raising=False)
    profile = UserProfile(str(tmp_path))
    config = profile.config
    config["sync"]["hub_url"] = "https://private.example.invalid"

    assert profile.user_id == "local-user"
    assert profile.display_name == "Local User"
    assert config["identity_mode"] == "anonymous"

    summary = profile.get_profile_summary()
    assert "local-user" not in summary
    assert "private.example.invalid" not in summary
    assert str(tmp_path) not in summary


def test_profile_uses_only_explicit_pseudonym_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("ELITE_USER_ID", "team-pseudonym-42")
    monkeypatch.setenv("ELITE_DISPLAY_NAME", "Release Team")

    profile = UserProfile(str(tmp_path))

    assert profile.user_id == "team-pseudonym-42"
    assert profile.display_name == "Release Team"
    assert profile.config["identity_mode"] == "explicit"


def test_profile_refreshes_pseudonym_from_environment_on_each_startup(tmp_path, monkeypatch):
    monkeypatch.delenv("ELITE_USER_ID", raising=False)
    monkeypatch.delenv("ELITE_DISPLAY_NAME", raising=False)
    anonymous = UserProfile(str(tmp_path))

    assert anonymous.user_id == "local-user"
    assert anonymous.config["identity_mode"] == "anonymous"

    monkeypatch.setenv("ELITE_USER_ID", "team-pseudonym-42")
    monkeypatch.setenv("ELITE_DISPLAY_NAME", "Release Team")
    explicit = UserProfile(str(tmp_path))

    assert explicit.user_id == "team-pseudonym-42"
    assert explicit.display_name == "Release Team"
    assert explicit.config["identity_mode"] == "explicit"

    monkeypatch.setenv("ELITE_USER_ID", "team-pseudonym-99")
    monkeypatch.setenv("ELITE_DISPLAY_NAME", "Platform Team")
    rotated = UserProfile(str(tmp_path))

    assert rotated.user_id == "team-pseudonym-99"
    assert rotated.display_name == "Platform Team"

    monkeypatch.delenv("ELITE_USER_ID")
    monkeypatch.delenv("ELITE_DISPLAY_NAME")
    reset = UserProfile(str(tmp_path))

    assert reset.user_id == "local-user"
    assert reset.display_name == "Local User"
    assert reset.config["identity_mode"] == "anonymous"


def test_remote_memory_is_quarantined_until_explicit_approval(tmp_path):
    store = EliteStore(str(tmp_path / "brain"))
    memory_id = store.record_memory_item(
        memory_type="remote_decision",
        content="Unverified remote instruction.",
        source="remote_sync",
        confidence=0.2,
        trust_score=0.2,
    )

    assert not store.search_memory_items("Unverified")
    quarantined = store.get_memory_item(memory_id, include_quarantined=True)
    assert quarantined is not None and quarantined["quarantined"] is True
    assert store.approve_memory_item(memory_id, trust_score=0.8) is True
    assert store.search_memory_items("Unverified")[0]["id"] == memory_id


def test_memory_secrets_are_redacted_at_rest_and_never_promoted(tmp_path):
    store = EliteStore(str(tmp_path / "brain"))
    secret = "sk-12345678901234567890"
    memory_id = store.record_memory_item(
        memory_type="credential",
        content=f"api_key={secret}",
        confidence=0.9,
        trust_score=0.9,
    )

    with sqlite3.connect(store.db_path) as conn:
        content, privacy_class, quarantined = conn.execute(
            "SELECT content, privacy_class, quarantined FROM memory_items WHERE id = ?",
            (memory_id,),
        ).fetchone()

    assert secret not in content
    assert "[REDACTED]" in content
    assert privacy_class == "secret_detected"
    assert quarantined == 1
    assert store.approve_memory_item(memory_id, trust_score=0.9) is False
    rendered = store.get_memory_item(memory_id, include_quarantined=True)
    assert rendered is not None
    assert secret not in rendered["content"]


def test_workflow_evidence_is_redacted_before_persistence(tmp_path):
    store = EliteStore(str(tmp_path / "brain"))
    secret = "sk-12345678901234567890"
    store.record_workflow_run(
        {"run_id": "evidence-private", "user_prompt": "Ship the fix.", "intent": "build"},
        [{"step_name": "validate", "action": "Run the release gate."}],
    )

    assert store.update_workflow_step(
        "evidence-private",
        1,
        "passed",
        f"validated with api_key={secret}",
    )

    with sqlite3.connect(store.db_path) as conn:
        raw_evidence = conn.execute(
            "SELECT evidence FROM workflow_steps WHERE run_id = ?",
            ("evidence-private",),
        ).fetchone()[0]

    workflow = store.get_workflow_run("evidence-private")
    assert secret not in raw_evidence
    assert "[REDACTED]" in raw_evidence
    assert workflow is not None
    assert secret not in workflow["steps"][0]["evidence"]


def test_privacy_migration_scrubs_legacy_prompt_telemetry_and_memory_rows(tmp_path):
    store = EliteStore(str(tmp_path / "brain"))
    secret = "sk-12345678901234567890"
    now = "2026-07-14 00:00:00"
    conn = store._connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM schema_migrations WHERE version = 6")
    cursor.execute(
        """INSERT INTO prompt_sessions
           (session_id, prompt_text, intent_category, reasoning_type, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("legacy", f"deploy with api_key={secret}", "build", "substantive", now),
    )
    cursor.execute(
        """INSERT INTO workflow_runs
           (run_id, user_prompt, intent, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("legacy-run", f"ship with api_key={secret}", "build", now, now),
    )
    cursor.execute(
        """INSERT INTO workflow_steps
           (run_id, step_index, step_name, action, status, evidence, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("legacy-run", 1, "validate", "validate", "passed", f"api_key={secret}", now, now),
    )
    cursor.execute(
        """INSERT INTO memory_items
           (memory_type, scope, source, content, privacy_class, content_hash, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("fact", "legacy", "manual", f"api_key={secret}", "internal", "legacy-secret", now, now),
    )
    cursor.execute(
        """INSERT INTO tool_usage_log
           (tool_name, args_summary, result_summary, created_at)
           VALUES (?, ?, ?, ?)""",
        ("legacy_tool", f"api_key={secret}", f"api_key={secret}", now),
    )

    store._run_privacy_migration(cursor)
    store._close(conn)

    with sqlite3.connect(store.db_path) as raw_conn:
        prompt_text = raw_conn.execute("SELECT prompt_text FROM prompt_sessions").fetchone()[0]
        user_prompt = raw_conn.execute("SELECT user_prompt FROM workflow_runs").fetchone()[0]
        evidence = raw_conn.execute("SELECT evidence FROM workflow_steps").fetchone()[0]
        content, privacy_class, quarantined = raw_conn.execute(
            "SELECT content, privacy_class, quarantined FROM memory_items"
        ).fetchone()
        args_summary, result_summary = raw_conn.execute(
            "SELECT args_summary, result_summary FROM tool_usage_log"
        ).fetchone()
        applied = raw_conn.execute(
            "SELECT version FROM schema_migrations WHERE version = 6"
        ).fetchone()

    assert secret not in prompt_text
    assert prompt_text.startswith("[prompt withheld;")
    assert secret not in user_prompt
    assert user_prompt.startswith("[prompt withheld;")
    assert secret not in evidence
    assert "[REDACTED]" in evidence
    assert secret not in content
    assert privacy_class == "secret_detected"
    assert quarantined == 1
    assert args_summary.startswith("sha256:")
    assert result_summary.startswith("sha256:")
    assert applied == (6,)


def test_sync_endpoint_requires_allowlisting_confirmation_and_network_opt_in(monkeypatch):
    monkeypatch.delenv("ELITE_SYNC_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("ELITE_SYNC_ALLOW_NETWORK", raising=False)

    assert validate_sync_endpoint("http://localhost:8000/") == "http://localhost:8000"
    with pytest.raises(ValueError, match="not approved"):
        validate_sync_endpoint("https://sync.example.com")

    monkeypatch.setenv("ELITE_SYNC_ALLOWED_HOSTS", "sync.example.com")
    assert validate_sync_endpoint("https://sync.example.com/") == "https://sync.example.com"
    with pytest.raises(PermissionError, match="confirm=true"):
        authorize_manual_sync("https://sync.example.com", confirmed=False)
    with pytest.raises(PermissionError, match="ELITE_SYNC_ALLOW_NETWORK"):
        authorize_manual_sync("https://sync.example.com", confirmed=True)

    monkeypatch.setenv("ELITE_SYNC_ALLOW_NETWORK", "1")
    assert authorize_manual_sync("https://sync.example.com", confirmed=True) == "https://sync.example.com"


@pytest.mark.asyncio
async def test_legacy_sync_requires_confirmation_and_quarantines_remote_records(tmp_path, monkeypatch):
    import httpx

    mcp = create_mcp_server(str(tmp_path / "brain"), tool_profile="legacy")
    sync_tool = mcp._tool_manager._tools["sync_team_memory"].fn

    def no_network(*_args, **_kwargs):
        raise AssertionError("network must not be called without confirm=true")

    monkeypatch.setattr(httpx, "get", no_network)
    denied = await sync_tool(confirm=False)
    assert "Sync access denied" in denied

    class PullResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "anti_patterns": [
                    {
                        "mistake": "Remote pattern",
                        "root_cause": "Unverified source",
                        "fix": "Review before use",
                    }
                ],
                "decisions": [
                    {
                        "decision": "Remote decision",
                        "context": "Remote source",
                        "rationale": "Needs review",
                    }
                ],
            }

    monkeypatch.setattr(httpx, "get", lambda *_args, **_kwargs: PullResponse())
    completed = await sync_tool(confirm=True, direction="pull")

    assert "quarantined remote records: 2" in completed
    records = mcp._elite_store.search_memory_items(
        scope="team",
        include_quarantined=True,
        min_trust=0.0,
    )
    assert len(records) == 2
    assert all(record["quarantined"] for record in records)
    assert {record["memory_type"] for record in records} == {"remote_anti_pattern", "remote_decision"}


@pytest.mark.asyncio
async def test_sync_uses_directional_cursors_and_replays_after_legacy_cursor(tmp_path, monkeypatch):
    import httpx

    monkeypatch.setenv("ELITE_SYNC_ALLOW_OUTBOUND", "1")
    monkeypatch.setenv("ELITE_USER_ID", "team-pseudonym-42")
    mcp = create_mcp_server(str(tmp_path / "brain"), tool_profile="legacy")
    store = mcp._elite_store
    store.record_mistake("Local sync record with enough detail", "A specific root cause is documented", "Apply a durable corrective action")
    cursor_path = tmp_path / "brain" / "sync_cursor.json"
    cursor_path.write_text(json.dumps({"last_synced_at": "2099-01-01T00:00:00+00:00"}), encoding="utf-8")
    sync_tool = mcp._tool_manager._tools["sync_team_memory"].fn

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    monkeypatch.setattr(httpx, "get", lambda *_args, **_kwargs: Response({"anti_patterns": [], "decisions": []}))
    await sync_tool(confirm=True, direction="pull")

    captured = {}

    def post(*_args, **kwargs):
        captured.update(kwargs["json"])
        return Response({"accepted": 1, "rejected": 0})

    monkeypatch.setattr(httpx, "post", post)
    completed = await sync_tool(confirm=True, direction="push")

    assert "1 accepted" in completed
    assert captured["anti_patterns"]
    assert captured["user_id"] == mcp._elite_profile.user_id == "team-pseudonym-42"
    cursor = json.loads(cursor_path.read_text(encoding="utf-8"))
    assert cursor["version"] == 2
    assert cursor["last_pulled_at"]
    assert cursor["last_pushed_at"]


@pytest.mark.asyncio
async def test_telemetry_off_does_not_write_usage_records(tmp_path, monkeypatch):
    monkeypatch.setenv("ELITE_TELEMETRY_MODE", "off")
    store = EliteStore(str(tmp_path / "brain"))
    middleware = UsageLogMiddleware(store)
    context = CallContext(tool_name="elite_prepare", args={"user_prompt": "private"}, session_id="test", started_at=0)

    await middleware.after(context, CallResult(value={"status": "ok"}, duration_ms=10))

    assert store.get_tool_usage_stats()["total_invocations"] == 0


def test_runtime_sources_do_not_include_developer_machine_paths_or_package_email():
    repository = Path(__file__).resolve().parents[1]
    source_files = [
        *(repository / "core").rglob("*.py"),
        *(repository / "app").rglob("*.py"),
        *(repository / "scripts").rglob("*.py"),
        repository / "run_sync_server.sh",
        repository / "Dockerfile",
        repository / "docker-compose.yml",
        repository / "telemetry-ui" / "src" / "app" / "actions" / "db.ts",
        repository / "pyproject.toml",
    ]

    for source_file in source_files:
        contents = source_file.read_text(encoding="utf-8")
        assert "/Users/" not in contents, source_file
        assert "snehgabani@gmail.com" not in contents, source_file
