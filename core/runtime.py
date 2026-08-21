"""Runtime identity and profile selection helpers for the MCP server."""

from __future__ import annotations

import importlib.metadata
import os
import shutil
import sys
from pathlib import Path
from typing import Literal

PACKAGE_NAME = "elite-reasoning-mcp"
ToolProfile = Literal["core", "legacy", "unified"]
SUPPORTED_TOOL_PROFILES: frozenset[str] = frozenset({"core", "legacy", "unified"})


def package_version() -> str:
    """Return the distribution version in both installed and source checkouts."""
    try:
        return importlib.metadata.version(PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        try:
            for line in pyproject.read_text(encoding="utf-8").splitlines():
                if line.startswith("version = "):
                    return line.split("=", 1)[1].strip().strip('"')
        except OSError as exc:
            # Source pyproject.toml not accessible in some execution contexts
            _ = str(exc)
    return "unknown"


def resolve_tool_profile(value: str | None = None) -> ToolProfile:
    """Resolve the public tool surface without silently accepting typos."""
    profile = (value or os.environ.get("ELITE_TOOL_PROFILE") or "core").strip().lower()
    if profile not in SUPPORTED_TOOL_PROFILES:
        choices = ", ".join(sorted(SUPPORTED_TOOL_PROFILES))
        raise ValueError(f"Invalid ELITE_TOOL_PROFILE `{profile}`. Choose one of: {choices}.")
    return profile  # type: ignore[return-value]


def runtime_identity() -> dict[str, str]:
    """Return the executable and distribution details needed to diagnose stale installs."""
    try:
        distribution_path = str(importlib.metadata.distribution(PACKAGE_NAME).locate_file(""))
    except importlib.metadata.PackageNotFoundError:
        distribution_path = str(Path(__file__).resolve().parents[1])

    argv_entrypoint = Path(sys.argv[0]).expanduser()
    if (argv_entrypoint.is_absolute() or "/" in sys.argv[0]) and argv_entrypoint.exists():
        entrypoint = argv_entrypoint
    else:
        interpreter_entrypoint = Path(sys.executable).parent / PACKAGE_NAME
        if interpreter_entrypoint.exists():
            entrypoint = interpreter_entrypoint
        else:
            entrypoint = Path(shutil.which(PACKAGE_NAME) or sys.argv[0]).expanduser()
    return {
        "package_name": PACKAGE_NAME,
        "package_version": package_version(),
        "python_executable": str(Path(sys.executable).resolve()),
        "entrypoint": str(entrypoint.resolve()),
        "distribution_path": distribution_path,
    }
