"""LATS-style Tree Search — v15 P0 #5 (the missing item from the original
five-item P0 scope).

Research base:
- LATS: Language Agent Tree Search Unifies Reasoning, Acting, and Planning
  in Language Models (Zhou et al., arXiv:2310.04406, ICML 2024) — UCB-guided
  tree search over reasoning steps: selection → expansion → evaluation →
  backpropagation, with value estimates guiding exploration.

Adaptation for this MCP (local stdio, no external tools): the "acting" axis
is N/A; we keep the reasoning+planning axes — explore multiple alternative
executions of the reasoning structure as a bounded tree, score nodes with a
faithfulness heuristic (meta-talk down-weighting, same insight that fixed
the v15 P0 #1 Arm-B failure mode), backprop value, and pick the best path.
Synthesis then executes the best branch. Fail-open: expand failures fall
back to the best node found so far. Deterministic when given scripted
expand/score functions (unit tests below require no LLM).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class _Node:
    id: int
    parent_id: int | None
    depth: int
    summary: str
    score: float = 0.0
    visits: int = 0
    children: list["_Node"] = field(default_factory=list)


def _ucb1(node: _Node, parent_visits: int, exploration: float) -> float:
    """Upper confidence bound: value estimate + exploration bonus. Standard
    LATS/tree-search selection criterion (Kocsis & Szepesvári UCT lineage)."""
    if node.visits == 0:
        return float("inf")
    return node.score + exploration * math.sqrt(
        math.log(max(parent_visits, 1)) / node.visits
    )


def lats_search(
    prompt: str,
    expand_fn: Callable[[str, int], list[str]],
    score_fn: Callable[[str], float],
    max_nodes: int = 6,
    max_depth: int = 2,
    branch_factor: int = 2,
    exploration: float = 1.0,
) -> dict[str, Any]:
    """Bounded LATS-style tree search over alternative reasonings.

    expand_fn(node_summary, depth) -> list of up to `branch_factor` child
    summaries (alternative continuations of the reasoning).
    score_fn(summary) -> float value estimate (higher = better).
    Returns best leaf summary + search stats. Never raises: expand_fn/score_fn
    exceptions are caught and the best node found so far is returned with
    `warnings` set.
    """
    t0 = time.monotonic()
    root = _Node(id=0, parent_id=None, depth=0, summary="")
    nodes: list[_Node] = [root]
    warnings: list[str] = []
    best = None

    def _to_dict(n: _Node) -> dict[str, Any]:
        return {
            "id": n.id,
            "depth": n.depth,
            "summary": n.summary[:400],
            "score": round(n.score, 4),
            "visits": n.visits,
        }

    frontier: list[_Node] = [root]
    while nodes.__len__() < max_nodes and frontier:
        # SELECT: highest-UCB frontier node (explore value + uncertainty).
        parent = max(
            frontier,
            key=lambda nd: _ucb1(
                nd,
                _by_id(nodes, nd.parent_id).visits if nd.parent_id is not None else 1,
                exploration,
            ),
        )
        if parent.depth >= max_depth:
            frontier.remove(parent)
            continue
        try:
            children_summaries = expand_fn(parent.summary, parent.depth) or []
        except Exception as e:  # noqa: BLE001 — fail-open per design
            warnings.append(f"lats expand failed at depth {parent.depth}: {e}")
            frontier.remove(parent)
            continue
        for cs in children_summaries[:branch_factor]:
            if nodes.__len__() >= max_nodes:
                break
            child = _Node(
                id=nodes.__len__(),
                parent_id=parent.id,
                depth=parent.depth + 1,
                summary=cs,
            )
            parent.children.append(child)
            nodes.append(child)
            try:
                child.score = float(score_fn(cs))
            except Exception as e:  # noqa: BLE001
                warnings.append(f"lats score failed: {e}")
                child.score = 0.0
            child.visits = 1
            # BACKPROP: walk ancestors, fold the child value in.
            anc = parent
            while anc is not None:
                anc.visits += 1
                anc.score = (anc.score * (anc.visits - 1) + child.score) / anc.visits
                anc = _by_id(nodes, anc.parent_id)
        # Replace parent with its children in the frontier (depth-first bias).
        frontier.remove(parent)
        frontier.extend(
            c for c in parent.children if c.depth < max_depth
        )
        if best is None or parent.score > best["score"]:
            best = _to_dict(parent)

    best_leaf = max(
        (n for n in nodes if n.children == [] and n.summary),
        key=lambda n: n.score,
        default=None,
    )
    chosen_node = (
        _to_dict(best_leaf)
        if best_leaf is not None
        else (best_from_nodes(nodes) or _to_dict(root))
    )
    chosen = dict(chosen_node)
    if best_leaf is None and warnings:
        chosen["warnings"] = warnings
    return {
        "best_summary": chosen["summary"],
        "best_score": chosen["score"],
        "nodes_explored": len(nodes) - 1,
        "max_depth_reached": max((n.depth for n in nodes), default=0),
        "search_duration_ms": int((time.monotonic() - t0) * 1000),
        "warnings": warnings,
    }


def best_from_nodes(nodes: list[_Node]) -> dict[str, Any] | None:
    """Highest-scored non-root node dict (used when no leaf is reachable)."""
    scored = [
        _to_dict(n) for n in nodes if n.summary
    ]
    return max(scored, key=lambda d: d["score"], default=None)


def _by_id(nodes: list[_Node], node_id: int | None) -> _Node | None:
    return next((n for n in nodes if n.id == node_id), None)