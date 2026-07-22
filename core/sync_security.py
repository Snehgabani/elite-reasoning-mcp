"""Client-side authorization checks for optional team synchronization."""

from __future__ import annotations

import os
from urllib.parse import urlparse

LOCAL_SYNC_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _allowed_hosts() -> set[str]:
    configured = os.environ.get("ELITE_SYNC_ALLOWED_HOSTS", "")
    hosts = {host.strip().lower() for host in configured.split(",") if host.strip()}
    return hosts or set(LOCAL_SYNC_HOSTS)


def is_local_sync_host(hostname: str) -> bool:
    return hostname.lower() in LOCAL_SYNC_HOSTS


def validate_sync_endpoint(url: str) -> str:
    """Validate one explicitly configured sync endpoint before any request is sent."""
    parsed = urlparse((url or "").strip())
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Sync URL must use http or https.")
    if not hostname:
        raise ValueError("Sync URL must include a hostname.")
    if parsed.username or parsed.password:
        raise ValueError("Sync URL must not contain credentials.")
    if hostname not in _allowed_hosts():
        raise ValueError(
            f"Sync host `{hostname}` is not approved. Set ELITE_SYNC_ALLOWED_HOSTS explicitly before using it."
        )
    if not is_local_sync_host(hostname) and parsed.scheme != "https":
        raise ValueError("Non-local sync endpoints must use https.")
    return parsed.geturl().rstrip("/")


def authorize_manual_sync(url: str, confirmed: bool) -> str:
    """Require both a configured host and explicit external-network permission."""
    endpoint = validate_sync_endpoint(url)
    hostname = (urlparse(endpoint).hostname or "").lower()
    if not confirmed:
        raise PermissionError("Sync is a network write. Re-run with confirm=true after user approval.")
    if not is_local_sync_host(hostname) and os.environ.get("ELITE_SYNC_ALLOW_NETWORK") != "1":
        raise PermissionError("Set ELITE_SYNC_ALLOW_NETWORK=1 to permit approved external sync hosts.")
    return endpoint
