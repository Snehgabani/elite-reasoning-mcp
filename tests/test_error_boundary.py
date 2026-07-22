"""Tests for protocol-safe tool error handling."""

import asyncio

import pytest

from core.tools.error_boundary import safe_tool, safe_tool_async
from core.tools.errors import EliteToolError, validation_error


class TestSafeToolHappyPath:
    def test_returns_normal_value(self):
        @safe_tool
        def add(a: int, b: int) -> int:
            return a + b

        assert add(2, 3) == 5

    def test_preserves_metadata(self):
        @safe_tool
        def documented(value: int) -> int:
            """A documented tool."""
            return value

        assert documented.__name__ == "documented"
        assert documented.__doc__ == "A documented tool."
        assert documented.__wrapped__.__annotations__["value"] is int


class TestSafeToolErrors:
    @pytest.mark.parametrize(
        ("exception", "leaked_text"),
        [
            (ValueError("bad value"), "bad value"),
            (RuntimeError("runtime bang"), "runtime bang"),
            (KeyError("missing"), "missing"),
        ],
    )
    def test_converts_unhandled_errors_to_sanitized_typed_errors(self, exception, leaked_text):
        @safe_tool
        def boom():
            raise exception

        with pytest.raises(EliteToolError) as raised:
            boom()

        error = raised.value
        assert error.code == "tool_execution_failed"
        assert "Tool `boom` failed safely" in error.message
        assert "error id:" in error.message
        assert leaked_text not in error.message

    def test_preserves_explicit_tool_errors(self):
        expected = validation_error("missing run id")

        @safe_tool
        def invalid():
            raise expected

        with pytest.raises(EliteToolError) as raised:
            invalid()

        assert raised.value is expected

    def test_double_wrapping_does_not_leak_the_original_exception(self):
        @safe_tool
        @safe_tool
        def double_boom():
            raise ValueError("double fail")

        with pytest.raises(EliteToolError) as raised:
            double_boom()

        assert "double fail" not in raised.value.message


class TestSafeToolAsync:
    def test_async_happy_path(self):
        @safe_tool_async
        async def add(a: int, b: int) -> int:
            return a + b

        assert asyncio.run(add(3, 4)) == 7

    def test_async_errors_are_typed_and_sanitized(self):
        @safe_tool_async
        async def boom():
            raise RuntimeError("async secret")

        async def run() -> EliteToolError:
            with pytest.raises(EliteToolError) as raised:
                await boom()
            return raised.value

        error = asyncio.run(run())
        assert error.code == "tool_execution_failed"
        assert "async secret" not in error.message
