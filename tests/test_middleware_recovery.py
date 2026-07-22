import pytest

from core.middleware.chain import MiddlewareChain
from core.middleware.fallback import FallbackMiddleware, RetryMiddleware
from core.tools.errors import EliteToolError


@pytest.mark.asyncio
async def test_retry_reexecutes_a_transient_failure():
    calls = 0

    async def flaky_tool(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise EliteToolError("busy", "database is locked", retryable=True)
        return {"status": "ok"}

    wrapped = MiddlewareChain().use(RetryMiddleware(max_retries=2, initial_delay=0)).wrap("flaky", flaky_tool)

    assert await wrapped() == {"status": "ok"}
    assert calls == 2


@pytest.mark.asyncio
async def test_final_failure_remains_an_error_with_fallback_guidance():
    async def broken_tool(**_kwargs):
        raise RuntimeError("connection refused")

    wrapped = (
        MiddlewareChain()
        .use(FallbackMiddleware({"broken": ["safe_alternative"]}))
        .use(RetryMiddleware(max_retries=0, initial_delay=0))
        .wrap("broken", broken_tool)
    )

    with pytest.raises(EliteToolError) as raised:
        await wrapped()

    assert raised.value.code == "tool_execution_failed"
    assert "Try: safe_alternative." in raised.value.message
