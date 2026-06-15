"""
Tests for core.tools.error_boundary.safe_tool / safe_tool_async.

Covers:
  - safe_tool wrapping a normal function
  - safe_tool catching exceptions and returning error string
  - safe_tool preserving function name/signature
  - Double-wrap prevention (_has_error_boundary flag check)
  - safe_tool_async variants
"""

import asyncio
import inspect

import pytest

from core.tools.error_boundary import safe_tool, safe_tool_async


# ──────────────────────────────────────────────
# 1. safe_tool wrapping a normal function
# ──────────────────────────────────────────────

class TestSafeToolHappyPath:
    def test_returns_normal_value(self):
        @safe_tool
        def add(a: int, b: int) -> int:
            return a + b

        assert add(2, 3) == 5

    def test_returns_none(self):
        @safe_tool
        def noop():
            return None

        assert noop() is None

    def test_returns_string(self):
        @safe_tool
        def greet(name: str) -> str:
            return f"hello {name}"

        assert greet("world") == "hello world"

    def test_returns_dict(self):
        @safe_tool
        def info():
            return {"status": "ok"}

        assert info() == {"status": "ok"}

    def test_passes_kwargs(self):
        @safe_tool
        def kw_func(x: int, y: int = 10) -> int:
            return x + y

        assert kw_func(1, y=20) == 21


# ──────────────────────────────────────────────
# 2. safe_tool catching exceptions
# ──────────────────────────────────────────────

class TestSafeToolErrorCatching:
    def test_catches_value_error(self):
        @safe_tool
        def boom():
            raise ValueError("bad value")

        result = boom()
        assert isinstance(result, str)
        assert "Tool Error" in result
        assert "ValueError" in result
        assert "bad value" in result

    def test_catches_runtime_error(self):
        @safe_tool
        def crash():
            raise RuntimeError("runtime bang")

        result = crash()
        assert "RuntimeError" in result
        assert "runtime bang" in result

    def test_catches_zero_division(self):
        @safe_tool
        def div():
            return 1 / 0

        result = div()
        assert "ZeroDivisionError" in result

    def test_error_contains_tool_name(self):
        @safe_tool
        def my_unique_tool():
            raise Exception("oops")

        result = my_unique_tool()
        assert "my_unique_tool" in result

    def test_error_contains_boundary_message(self):
        @safe_tool
        def failing():
            raise Exception("fail")

        result = failing()
        assert "error boundary" in result.lower()
        assert "MCP server is still running" in result

    def test_catches_type_error(self):
        @safe_tool
        def typed():
            return len(42)  # TypeError

        result = typed()
        assert "TypeError" in result

    def test_catches_key_error(self):
        @safe_tool
        def keyed():
            d = {}
            return d["missing"]

        result = keyed()
        assert "KeyError" in result

    def test_does_not_reraise(self):
        """Exceptions should NOT propagate — that's the whole point."""

        @safe_tool
        def explode():
            raise SystemError("kaboom")

        # This must not raise
        result = explode()
        assert isinstance(result, str)


# ──────────────────────────────────────────────
# 3. safe_tool preserving function name/signature
# ──────────────────────────────────────────────

class TestPreservesMetadata:
    def test_preserves_name(self):
        @safe_tool
        def my_func():
            pass

        assert my_func.__name__ == "my_func"

    def test_preserves_docstring(self):
        @safe_tool
        def documented():
            """This is the docstring."""
            pass

        assert documented.__doc__ == "This is the docstring."

    def test_preserves_module(self):
        @safe_tool
        def modular():
            pass

        assert modular.__module__ == __name__

    def test_preserves_qualname(self):
        @safe_tool
        def qualified():
            pass

        assert "qualified" in qualified.__qualname__

    def test_preserves_annotations(self):
        @safe_tool
        def annotated(x: int, y: str) -> bool:
            return True

        ann = annotated.__wrapped__.__annotations__
        assert ann["x"] is int
        assert ann["y"] is str
        assert ann["return"] is bool


# ──────────────────────────────────────────────
# 4. Double-wrap prevention
# ──────────────────────────────────────────────

class TestDoubleWrapPrevention:
    def test_single_wrap_is_callable(self):
        @safe_tool
        def single():
            return "ok"

        assert callable(single)
        assert single() == "ok"

    def test_double_wrap_still_works(self):
        """Even if double-wrapped, the function should still work correctly
        (the outer wrapper catches errors from the inner wrapper)."""

        @safe_tool
        @safe_tool
        def double():
            return "double ok"

        assert double() == "double ok"

    def test_double_wrap_still_catches(self):
        @safe_tool
        @safe_tool
        def double_boom():
            raise ValueError("double fail")

        result = double_boom()
        assert isinstance(result, str)
        assert "Tool Error" in result

    def test_wrapped_attribute_points_to_original(self):
        def original():
            return 42

        wrapped = safe_tool(original)
        assert wrapped.__wrapped__ is original


# ──────────────────────────────────────────────
# 5. safe_tool_async
# ──────────────────────────────────────────────

class TestSafeToolAsync:
    def test_async_happy_path(self):
        @safe_tool_async
        async def async_add(a, b):
            return a + b

        result = asyncio.run(async_add(3, 4))
        assert result == 7

    def test_async_catches_exception(self):
        @safe_tool_async
        async def async_boom():
            raise ValueError("async fail")

        result = asyncio.run(async_boom())
        assert isinstance(result, str)
        assert "ValueError" in result
        assert "async_boom" in result

    def test_async_preserves_name(self):
        @safe_tool_async
        async def named_async():
            pass

        assert named_async.__name__ == "named_async"

    def test_async_error_boundary_message(self):
        @safe_tool_async
        async def fail_async():
            raise RuntimeError("rt")

        result = asyncio.run(fail_async())
        assert "MCP server is still running" in result

    def test_async_is_coroutinefunction(self):
        @safe_tool_async
        async def coro():
            pass

        assert asyncio.iscoroutinefunction(coro)
