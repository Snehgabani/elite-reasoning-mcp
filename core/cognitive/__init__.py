"""Optional legacy cognitive runtime.

The default verification server imports selected deterministic submodules lazily.
Keeping this package initializer side-effect free prevents a syntax check from
loading graph runtimes, model adapters, and the global cognitive engine.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.cognitive.engine import EliteCognitiveEngine, _COGNITIVE_ENGINE, _MIX_ENGINE
    from core.cognitive.leverage.deterministic_gates import (
        apply_verified_diff,
        generate_diff_hmac,
        validate_diff_integrity,
        validate_math_invariants,
        validate_security_invariants,
        validate_syntax,
    )
    from core.cognitive.leverage.enforcer import GatedEnforcer
    from core.cognitive.leverage.logic_verifier import LogicVerifier
    from core.cognitive.leverage.prm_verifier import ProcessRewardModel
    from core.cognitive.leverage.task_watcher import TaskTracker

_EXPORTS: dict[str, tuple[str, str]] = {
    "EliteCognitiveEngine": ("core.cognitive.engine", "EliteCognitiveEngine"),
    "_COGNITIVE_ENGINE": ("core.cognitive.engine", "_COGNITIVE_ENGINE"),
    "_MIX_ENGINE": ("core.cognitive.engine", "_MIX_ENGINE"),
    "ProcessRewardModel": ("core.cognitive.leverage.prm_verifier", "ProcessRewardModel"),
    "LogicVerifier": ("core.cognitive.leverage.logic_verifier", "LogicVerifier"),
    "GatedEnforcer": ("core.cognitive.leverage.enforcer", "GatedEnforcer"),
    "TaskTracker": ("core.cognitive.leverage.task_watcher", "TaskTracker"),
    "validate_syntax": ("core.cognitive.leverage.deterministic_gates", "validate_syntax"),
    "validate_security_invariants": (
        "core.cognitive.leverage.deterministic_gates",
        "validate_security_invariants",
    ),
    "validate_math_invariants": ("core.cognitive.leverage.deterministic_gates", "validate_math_invariants"),
    "validate_diff_integrity": ("core.cognitive.leverage.deterministic_gates", "validate_diff_integrity"),
    "apply_verified_diff": ("core.cognitive.leverage.deterministic_gates", "apply_verified_diff"),
    "generate_diff_hmac": ("core.cognitive.leverage.deterministic_gates", "generate_diff_hmac"),
}

__all__ = [
    "EliteCognitiveEngine",
    "_COGNITIVE_ENGINE",
    "_MIX_ENGINE",
    "ProcessRewardModel",
    "LogicVerifier",
    "GatedEnforcer",
    "TaskTracker",
    "validate_syntax",
    "validate_security_invariants",
    "validate_math_invariants",
    "validate_diff_integrity",
    "apply_verified_diff",
    "generate_diff_hmac",
]


def __getattr__(name: str) -> Any:
    """Load compatibility exports only when a caller explicitly requests one."""
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
