"""Privacy-safe local telemetry and prompt-storage helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Literal

TelemetryMode = Literal["off", "metadata", "summary", "raw"]
_VALID_TELEMETRY_MODES = frozenset({"off", "metadata", "summary", "raw"})

_KEY_VALUE_SECRET = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|auth(?:orization)?|password|secret|cookie)"
    r"(\s*[:=]\s*)([^,\s}\]\n]+)"
)
_JSON_SECRET = re.compile(
    r"(?i)([\"']?(?:api[_-]?key|access[_-]?token|auth(?:orization)?|password|secret|cookie)[\"']?\s*:\s*[\"'])[^\"']*([\"'])"
)
_BEARER_TOKEN = re.compile(r"(?i)(bearer\s+)[a-z0-9._~+\-/=]+")
_OPENAI_TOKEN = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
_GITHUB_TOKEN = re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")
_GOOGLE_API_KEY = re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----", re.DOTALL)


def _serialize(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)


def redact_text(value: Any, limit: int = 500) -> str:
    """Remove common secret forms before a value reaches telemetry or logs."""
    text = _serialize(value)
    text = _PRIVATE_KEY.sub("[REDACTED_PRIVATE_KEY]", text)
    text = _JSON_SECRET.sub(r"\1[REDACTED]\2", text)
    # Bearer credentials must be removed before generic key/value handling.
    # Otherwise ``Authorization: Bearer <token>`` leaves the token intact.
    text = _BEARER_TOKEN.sub(r"\1[REDACTED]", text)
    text = _KEY_VALUE_SECRET.sub(r"\1\2[REDACTED]", text)
    text = _OPENAI_TOKEN.sub("[REDACTED_OPENAI_KEY]", text)
    text = _GITHUB_TOKEN.sub("[REDACTED_GITHUB_TOKEN]", text)
    text = _GOOGLE_API_KEY.sub("[REDACTED_GOOGLE_KEY]", text)
    return text[:limit]


def _fingerprint(value: Any) -> str:
    text = _serialize(value)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"sha256:{digest};chars:{len(text)}"


def metadata_fingerprint(value: Any) -> str:
    """Return a stable metadata-only representation without retaining content."""
    return _fingerprint(value)


def withheld_prompt_value(prompt_text: str) -> str:
    """Represent a prompt without retaining its raw content."""
    return f"[prompt withheld; {_fingerprint(prompt_text)}]"


def telemetry_mode() -> TelemetryMode:
    """Default to metadata-only telemetry; raw mode requires a second opt-in."""
    mode = os.environ.get("ELITE_TELEMETRY_MODE", "metadata").strip().lower()
    if mode not in _VALID_TELEMETRY_MODES:
        return "metadata"
    if mode == "raw" and os.environ.get("ELITE_ALLOW_RAW_TELEMETRY") != "1":
        return "metadata"
    return mode  # type: ignore[return-value]


def telemetry_summary(value: Any) -> str:
    """Render a safe telemetry value according to the explicit storage policy."""
    mode = telemetry_mode()
    if mode == "off":
        return ""
    if mode == "metadata":
        return metadata_fingerprint(value)
    return redact_text(value)


def prompt_storage_value(prompt_text: str) -> str:
    """Store raw prompt text only after an explicit local opt-in."""
    if raw_prompt_storage_enabled():
        return redact_text(prompt_text, limit=5000)
    return withheld_prompt_value(prompt_text)


def raw_prompt_storage_enabled() -> bool:
    """Whether local raw-prompt retention has been explicitly enabled."""
    return os.environ.get("ELITE_ALLOW_RAW_PROMPT_STORAGE") == "1"


def safe_error_detail(error: Exception | str, limit: int = 200) -> str:
    """Keep server-side diagnostics useful without retaining secrets in logs."""
    return redact_text(str(error), limit=limit)
