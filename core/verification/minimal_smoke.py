"""Installed-wheel smoke check for the dependency-light core profile."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
from typing import Any

FORBIDDEN_CORE_DISTRIBUTIONS = ("fastapi", "langchain", "langchain_openai", "langgraph", "networkx", "scipy")
CORE_TOOLS = {"elite_prepare", "elite_verify", "elite_memory"}


async def _run() -> None:
    unavailable = [name for name in FORBIDDEN_CORE_DISTRIBUTIONS if importlib.util.find_spec(name) is not None]
    if unavailable:
        raise RuntimeError("optional packages leaked into minimal core installation: " + ", ".join(unavailable))

    from core.integration.mcp_server import create_mcp_server

    with tempfile.TemporaryDirectory(prefix="elite-minimal-core-") as brain_dir:
        server: Any = create_mcp_server(brain_dir, tool_profile="core")
        tools = set(server._tool_manager._tools)
        if tools != CORE_TOOLS:
            raise RuntimeError(f"unexpected core tool surface: {sorted(tools)}")
        syntax = await server._tool_manager._tools["elite_verify"].fn(check="syntax", code="value = 1")
        if syntax.verification_status.value != "PASS":
            raise RuntimeError(f"minimal syntax verification failed: {syntax.verification_status}")

    forbidden_imports = sorted(
        name for name in sys.modules if name.startswith(("fastapi", "langchain", "langgraph", "networkx", "scipy"))
    )
    if forbidden_imports:
        raise RuntimeError("optional modules loaded by core smoke: " + ", ".join(forbidden_imports[:20]))


def main() -> int:
    asyncio.run(_run())
    print("minimal_core=ok tools=5 syntax=PASS optional_imports=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
