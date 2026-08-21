"""
Elite Cognitive Singularity Package.
Exposes the 9-stage cognitive engine, PRMs, AST invariant gates, and closed-loop reasoning graphs.
"""
from core.cognitive.engine import EliteCognitiveEngine, _COGNITIVE_ENGINE, _MIX_ENGINE
from core.cognitive.leverage.prm_verifier import ProcessRewardModel
from core.cognitive.leverage.logic_verifier import LogicVerifier
from core.cognitive.leverage.enforcer import GatedEnforcer
from core.cognitive.leverage.task_watcher import TaskTracker
from core.cognitive.leverage.deterministic_gates import (
    validate_syntax,
    validate_security_invariants,
    validate_math_invariants,
    validate_diff_integrity,
    apply_verified_diff,
    generate_diff_hmac,
)

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
