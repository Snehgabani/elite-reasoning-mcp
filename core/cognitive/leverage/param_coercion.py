"""
Pure-Python Deterministic Parameter Coercion & JSON Repair Engine.
Enables cheap/small models (7B/8B, GPT-4o-mini, Flash-Lite) to execute tool calls
reliably without suffering from parameter type mismatch, malformed JSON, or markdown fence errors.
Operates deterministically in <0.05ms without LLM round-trips.
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union


class ParameterCoercionEngine:
    """
    Deterministic AST interceptor that repairs malformed JSON, coerces types according
    to expected schemas, and strips noisy markdown artifacts.
    """

    @classmethod
    def strip_fences_and_noise(cls, raw_text: str) -> str:
        """Strips markdown code fences, conversational preambles, and postscripts."""
        if not raw_text:
            return ""
        text = raw_text.strip()

        # 1. Strip standard ```json ... ``` or ``` ... ```
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.I)
        if fence_match:
            text = fence_match.group(1).strip()

        # 2. If there is still conversational text before the first { or [
        first_bracket = min(
            [pos for pos in (text.find("{"), text.find("[")) if pos != -1],
            default=-1,
        )
        if first_bracket > 0:
            text = text[first_bracket:]

        # 3. Strip conversational text after the last } or ]
        last_bracket = max(text.rfind("}"), text.rfind("]"))
        if last_bracket != -1 and last_bracket < len(text) - 1:
            text = text[: last_bracket + 1]

        return text.strip()

    @classmethod
    def repair_json_string(cls, raw_text: str) -> str:
        """
        Fixes common small-model syntax defects:
        - Trailing commas before closing brackets/braces
        - Unquoted object keys
        - Single-quoted strings
        - Python literals (True, False, None) -> (true, false, null)
        """
        text = cls.strip_fences_and_noise(raw_text)
        if not text:
            return "{}"

        # Try fast path
        try:
            json.loads(text)
            return text
        except Exception:
            pass

        # 1. Replace trailing commas: ,} -> } and ,] -> ]
        text = re.sub(r",\s*([\]}])", r"\1", text)

        # 2. Replace unquoted keys: { key: ... } -> { "key": ... }
        text = re.sub(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_-]*)\s*:", r'\1"\2":', text)

        # 3. Convert single quoted string values to double quotes: 'value' -> "value"
        text = re.sub(r":\s*'([^']*)'", r': "\1"', text)

        # 4. Replace Python boolean/null literals if not inside quotes
        text = re.sub(r"(?<=[\s:\[,])True(?=[\s,\]}])", "true", text)
        text = re.sub(r"(?<=[\s:\[,])False(?=[\s,\]}])", "false", text)
        text = re.sub(r"(?<=[\s:\[,])None(?=[\s,\]}])", "null", text)

        # 5. Try parsing repaired text
        try:
            json.loads(text)
            return text
        except Exception:
            pass

        # 6. If single quotes are used, convert cleanly via ast.literal_eval if safe
        try:
            cleaned_ast = cls.strip_fences_and_noise(raw_text)
            cleaned_ast = re.sub(r",\s*([\]}])", r"\1", cleaned_ast)
            cleaned_ast = re.sub(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_-]*)\s*:", r'\1"\2":', cleaned_ast)
            parsed = ast.literal_eval(cleaned_ast)
            if isinstance(parsed, (dict, list)):
                return json.dumps(parsed)
        except Exception:
            pass

        return text

    @classmethod
    def parse_and_repair(cls, raw_text: str) -> Dict[str, Any]:
        """
        Safely parses JSON with fallback repairs. Returns a dictionary guarantee.
        """
        repaired_text = cls.repair_json_string(raw_text)
        try:
            res = json.loads(repaired_text)
            if isinstance(res, dict):
                return res
            return {"payload": res}
        except Exception:
            pass

        # Last-ditch AST literal_eval fallback
        try:
            cleaned = cls.strip_fences_and_noise(raw_text)
            cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)
            cleaned = re.sub(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_-]*)\s*:", r"\1\"\2\":", cleaned)
            res = ast.literal_eval(cleaned)
            if isinstance(res, dict):
                return res
            return {"payload": res}
        except Exception:
            pass

        # Structured salvage
        return {
            "raw_content": raw_text.strip(),
            "parse_error": "unparseable_output",
            "salvaged": True,
        }

    @classmethod
    def coerce_parameters(
        cls,
        args: Dict[str, Any],
        expected_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Coerces argument types according to the expected JSON schema:
        - \"42\" -> 42 (when int expected)
        - \"3.14\" -> 3.14 (when float/number expected)
        - \"true\" / \"1\" / \"yes\" -> True (when boolean expected)
        - scalar -> list (when array expected)
        - JSON string -> dict/list (when object/array expected)
        """
        if not expected_schema:
            return args

        properties = expected_schema.get("properties", {})
        if not properties or not isinstance(properties, dict):
            return args

        coerced = dict(args)

        for param_name, prop_def in properties.items():
            if param_name not in coerced:
                if "default" in prop_def:
                    coerced[param_name] = prop_def["default"]
                continue

            val = coerced[param_name]
            prop_type = prop_def.get("type")

            if prop_type == "integer":
                coerced[param_name] = cls._coerce_int(val, prop_def.get("default", 0))
            elif prop_type == "number":
                coerced[param_name] = cls._coerce_float(val, prop_def.get("default", 0.0))
            elif prop_type == "boolean":
                coerced[param_name] = cls._coerce_bool(val, prop_def.get("default", False))
            elif prop_type == "array":
                coerced[param_name] = cls._coerce_list(val)
            elif prop_type == "string":
                if not isinstance(val, str):
                    coerced[param_name] = str(val) if val is not None else ""
            elif prop_type == "object":
                if isinstance(val, str):
                    coerced[param_name] = cls.parse_and_repair(val)

        return coerced

    @staticmethod
    def _coerce_int(val: Any, default: int = 0) -> int:
        if isinstance(val, int) and not isinstance(val, bool):
            return val
        if isinstance(val, float):
            return int(val)
        if isinstance(val, str):
            cleaned = val.strip()
            try:
                return int(cleaned)
            except ValueError:
                try:
                    return int(float(cleaned))
                except ValueError:
                    pass
        return default

    @staticmethod
    def _coerce_float(val: Any, default: float = 0.0) -> float:
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val)
        if isinstance(val, str):
            cleaned = val.strip()
            try:
                return float(cleaned)
            except ValueError:
                pass
        return default

    @staticmethod
    def _coerce_bool(val: Any, default: bool = False) -> bool:
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            low = val.strip().lower()
            if low in ("true", "1", "yes", "y", "t", "on", "enable", "enabled"):
                return True
            if low in ("false", "0", "no", "n", "f", "off", "disable", "disabled"):
                return False
        return default

    @staticmethod
    def _coerce_list(val: Any) -> List[Any]:
        if isinstance(val, list):
            return val
        if isinstance(val, tuple):
            return list(val)
        if isinstance(val, str):
            cleaned = val.strip()
            if cleaned.startswith("[") and cleaned.endswith("]"):
                try:
                    parsed = json.loads(cleaned)
                    if isinstance(parsed, list):
                        return parsed
                except Exception:
                    pass
            if "," in cleaned:
                return [item.strip() for item in cleaned.split(",") if item.strip()]
            if cleaned:
                return [cleaned]
            return []
        if val is not None:
            return [val]
        return []
