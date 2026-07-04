import importlib

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
