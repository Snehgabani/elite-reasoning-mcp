import importlib
import json

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_sync_auth_fails_closed_without_key(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SYNC_API_KEY", raising=False)
    monkeypatch.delenv("ELITE_SYNC_SERVER_KEY", raising=False)
    monkeypatch.delenv("ELITE_ALLOW_OPEN_SYNC", raising=False)

    import core.integration.sync_server as sync_server

    sync_server = importlib.reload(sync_server)

    with pytest.raises(HTTPException) as exc:
        await sync_server.get_api_key(None)

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_sync_auth_allows_explicit_dev_open_mode(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SYNC_API_KEY", raising=False)
    monkeypatch.delenv("ELITE_SYNC_SERVER_KEY", raising=False)
    monkeypatch.setenv("ELITE_ALLOW_OPEN_SYNC", "1")

    import core.integration.sync_server as sync_server

    sync_server = importlib.reload(sync_server)

    assert await sync_server.get_api_key(None) is None


@pytest.mark.asyncio
async def test_sync_auth_accepts_configured_key(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNC_API_KEY", "secret")
    monkeypatch.delenv("ELITE_SYNC_SERVER_KEY", raising=False)
    monkeypatch.delenv("ELITE_ALLOW_OPEN_SYNC", raising=False)

    import core.integration.sync_server as sync_server

    sync_server = importlib.reload(sync_server)

    assert await sync_server.get_api_key("secret") == "secret"
    with pytest.raises(HTTPException) as exc:
        await sync_server.get_api_key("wrong")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_sync_actor_is_bound_to_a_per_user_credential(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SYNC_API_KEY", raising=False)
    monkeypatch.delenv("ELITE_SYNC_SERVER_KEY", raising=False)
    monkeypatch.delenv("ELITE_ALLOW_OPEN_SYNC", raising=False)
    monkeypatch.setenv("SYNC_USER_KEYS_JSON", json.dumps({"alice": "alice-key", "bob": "bob-key"}))

    import core.integration.sync_server as sync_server

    sync_server = importlib.reload(sync_server)
    assert await sync_server.get_sync_actor("alice-key") == "alice"
    assert await sync_server.get_sync_actor("bob-key") == "bob"


def test_sync_payload_rejects_malformed_or_empty_team_records(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNC_API_KEY", "test-key")
    monkeypatch.delenv("SYNC_USER_KEYS_JSON", raising=False)

    import core.integration.sync_server as sync_server

    sync_server = importlib.reload(sync_server)
    with pytest.raises(Exception):
        sync_server.SyncPayload(anti_patterns=[{"mistake": ["not text"], "root_cause": "cause", "fix": "fix"}])
    with pytest.raises(Exception):
        sync_server.SyncPayload(decisions=[{"decision": "", "rationale": "missing decision"}])


@pytest.mark.asyncio
async def test_external_llm_judge_requires_a_separate_explicit_opt_in(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNC_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-provider-key")
    monkeypatch.delenv("ELITE_SYNC_ENABLE_LLM_JUDGE", raising=False)

    import core.integration.sync_server as sync_server

    sync_server = importlib.reload(sync_server)
    passed, reason = await sync_server.evaluate_quality(
        {
            "mistake": "A detailed production incident description",
            "root_cause": "A detailed root cause analysis exists",
            "fix": "A detailed corrective action exists",
        }
    )
    assert passed is True
    assert reason == "Passed (Heuristic Only)"


def test_sync_hub_binds_locally_and_requires_two_explicit_external_guards(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SYNC_API_KEY", raising=False)
    monkeypatch.delenv("ELITE_SYNC_SERVER_KEY", raising=False)
    monkeypatch.delenv("ELITE_ALLOW_OPEN_SYNC", raising=False)
    monkeypatch.delenv("ELITE_SYNC_BIND_ALL_INTERFACES", raising=False)
    monkeypatch.delenv("SYNC_HOST", raising=False)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")

    import core.integration.sync_server as sync_server

    sync_server = importlib.reload(sync_server)
    assert sync_server.sync_bind_host() == "127.0.0.1"
    assert "*" not in sync_server._cors_origins

    monkeypatch.setenv("SYNC_HOST", "0.0.0.0")
    with pytest.raises(RuntimeError, match="ELITE_SYNC_BIND_ALL_INTERFACES"):
        sync_server.sync_bind_host()

    monkeypatch.setenv("ELITE_SYNC_BIND_ALL_INTERFACES", "1")
    with pytest.raises(RuntimeError, match="requires SYNC_API_KEY"):
        sync_server.sync_bind_host()

    monkeypatch.setenv("SYNC_API_KEY", "test-key")
    sync_server = importlib.reload(sync_server)
    assert sync_server.sync_bind_host() == "0.0.0.0"
