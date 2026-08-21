"""Deterministic reasoning scaffolds for Elite Reasoning MCP."""

from core.reasoning.constraint_check import check_draft
from core.reasoning.experiment_tree import build_experiment_tree, experiment_tree_markdown
from core.reasoning.nuclear_prompt import (
    break_down_prompt,
    nuclear_prompt_markdown,
    protocol_recommendation_markdown,
    select_reasoning_protocol,
)
from core.reasoning.playbook import playbook_card, verify_outcomes
from core.reasoning.task_contract import compile_task_contract

__all__ = [
    "break_down_prompt",
    "build_experiment_tree",
    "check_draft",
    "compile_task_contract",
    "playbook_card",
    "verify_outcomes",
    "experiment_tree_markdown",
    "nuclear_prompt_markdown",
    "protocol_recommendation_markdown",
    "select_reasoning_protocol",
]
