"""Adaptive Self-Consistency (RASC-style) — v15 P0 #1.

Research base: "Reasoning-Aware Self-Consistency: Leveraging Reasoning Paths
for Efficient LLM Sampling" (arXiv:2408.17017, NAACL 2025). Key findings
implemented here:

1. **Criteria-based early stopping** — stop sampling once a stable majority
   emerges instead of always drawing a fixed N; cuts sample usage ~70% at
   equal accuracy.
2. **Faithfulness-weighted voting** — weight each sampled path by a
   faithfulness score (not just count it), so reasoning paths that degrade
   into planning meta-talk or truncated drafts get down-weighted.

Design constraints (this project):
- stdlib only (urllib/json/difflib) — no new deps.
- The synthesis LLM is the local proxy (127.0.0.1:4096, gpt-oss:20b); the
  LLM call is injectable so tests can script deterministic answers.
- Fail-open: if the LLM is unavailable, return empty so the caller falls
  back to scaffolding-only output exactly like v14 did.

Telemetry: records `consensus_samples`, `consensus_agreement`,
`consensus_faithfulness_mean` via the store.
"""

from __future__ import annotations

import difflib
import json
import re
import time
import urllib.request
from typing import Any, Callable

_LLM_PROXY_URL = "http://127.0.0.1:4096/v1/chat/completions"
_LLM_MODEL = "gpt-oss:20b"

# Planning meta-talk markers — the failure mode measured in the 08-12 A/B
# (Arm B q7: "We need to explain tradeoffs... Provide details: ..." with NO
# answer). Paths containing these are down-weighted, not discarded.
_META_TALK_RE = re.compile(
    r"\b(we need to|let me (?:outline|explain|think|start)|"
    r"provide details|discuss aspects|in this (?:section|answer) we will|"
    r"here is (?:the )?plan|my approach would be)\b",
    re.IGNORECASE,
)

# Truncation markers (reasoning model stopped mid-draft).
_TRUNCATION_RE = re.compile(r"\b(?:\.\.\.|…)$", re.MULTILINE)


def _default_llm_call(prompt: str, temperature: float) -> tuple[str, str]:
    """Call the local LLM proxy. Returns (answer, model). Empty on failure."""
    body = json.dumps(
        {
            "model": _LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": temperature,
        }
    ).encode()
    req = urllib.request.Request(_LLM_PROXY_URL, data=body, headers={"Content-Type": "application/json"})
    last_err: Exception | None = None
    for _ in range(2):  # one retry on transient failure (self-diagnosis fix, 08-12)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            msg = data["choices"][0]["message"]
            answer = (msg.get("content") or "").strip()
            if not answer:
                answer = (msg.get("reasoning") or "").strip()  # reasoning-model field
            if answer:
                return answer, _LLM_MODEL
            last_err = RuntimeError("empty completion")
        except Exception as e:  # noqa: BLE001
            last_err = e
    if last_err is not None:
        raise last_err
    return "", ""


def faithfulness_score(answer: str) -> float:
    """Heuristic faithfulness: how much does this path read like a complete,
    direct answer rather than planning meta-talk or a truncated draft?

    Returns 0.0–1.0. The heuristic mirrors the rubric dimensions that
    separated Arm A from Arm B in the 08-12 efficacy A/B (completeness,
    actionability, absence of meta-talk)."""
    if not answer:
        return 0.0
    text = answer.strip()
    score = 1.0
    # 1. Meta-talk penalty: planning text instead of executing.
    meta_hits = len(_META_TALK_RE.findall(text))
    if meta_hits:
        score -= 0.25 * min(meta_hits, 3)
    # 2. Truncation penalty: answer that cuts off mid-thought.
    if _TRUNCATION_RE.search(text) or text.endswith((":", "and", "the", "to")):
        score -= 0.3
    # 3. Completeness: very short answers carry little evidence mass.
    words = len(text.split())
    if words < 30:
        score -= 0.3
    elif words < 60:
        score -= 0.1
    return max(0.0, min(1.0, score))


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _greedy_clusters(answers: list[dict[str, Any]], sim_threshold: float = 0.5) -> list[list[int]]:
    """Cluster sampled answers by normalized string similarity (greedy,
    order-independent enough for small N). Returns list of index-lists."""
    clusters: list[list[int]] = []
    for i, ans in enumerate(answers):
        placed = False
        for cl in clusters:
            # Compare against the cluster's first member (representative).
            rep = answers[cl[0]]
            if _similarity(ans["answer"], rep["answer"]) >= sim_threshold:
                cl.append(i)
                placed = True
                break
        if not placed:
            clusters.append([i])
    return clusters


from concurrent.futures import ThreadPoolExecutor


def run_adaptive_consensus(
    prompt: str,
    template: str,
    llm_call: Callable[[str, float], tuple[str, str]] | None = None,
    min_samples: int = 3,
    max_samples: int = 5,
    stop_fraction: float = 0.6,
    sim_threshold: float = 0.5,
    temperature_range: tuple[float, float] = (0.2, 0.6),
) -> dict[str, Any]:
    """Run RASC-style adaptive self-consistency over the reasoning structure in parallel.

    Args:
        prompt: original user task.
        template: the pipeline-generated reasoning structure (from
            PipelineResult.reasoning_template).
        llm_call: injectable (prompt, temperature) -> (answer, model). Defaults
            to the local proxy. Tests script this.
        min_samples: minimum samples before early-stop is allowed.
        max_samples: hard cap (RASC: adaptive, but bounded — no unbounded loops).
        stop_fraction: fraction of samples in the largest cluster required to
            stop early.
        sim_threshold: cluster similarity threshold (0-1).
        temperature_range: jitter for path diversity (RASC samples diverse
            reasoning paths; diversity is what makes voting meaningful).

    Returns dict with keys: answer, model, samples_used, agreement,
    faithfulness_mean, path_scores, stopped_early. On LLM failure: answer="",
    model="" (caller falls back to scaffolding-only, exactly like v14).
    """
    call = llm_call or _default_llm_call
    executor_prompt = (
        "You are a reasoning executor. A structured reasoning pipeline "
        "produced the analysis structure below for the task. Execute the "
        "reasoning end-to-end and deliver a complete, concrete, final "
        "answer. Do not describe the structure — produce the answer.\n\n"
        f"TASK: {prompt}\n\nREASONING STRUCTURE:\n{template}\n\nFINAL ANSWER:"
    )

    t0 = time.monotonic()

    def _sample_single(i: int) -> dict[str, Any] | None:
        frac = i / max(1, max_samples - 1)
        temp = temperature_range[0] + frac * (temperature_range[1] - temperature_range[0])
        try:
            ans, model = call(executor_prompt, temp)
        except Exception:
            ans, model = "", ""
        if not ans:
            return None
        return {
            "sample_index": i,
            "answer": ans,
            "model": model,
            "faithfulness": faithfulness_score(ans),
            "temperature": temp,
        }

    # Batch 1: Initial min_samples in parallel
    initial_indices = list(range(min_samples))
    answers: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max(1, len(initial_indices))) as pool:
        results = list(pool.map(_sample_single, initial_indices))
        for res in results:
            if res is not None:
                answers.append(res)

    if not answers:
        return {
            "answer": "",
            "model": "",
            "samples_used": 0,
            "agreement": 0.0,
            "faithfulness_mean": 0.0,
            "path_scores": [],
            "stopped_early": False,
        }

    samples_used = len(answers)
    stopped_early = False

    # Check early stopping on initial batch if full min_samples succeeded
    if samples_used >= min_samples:
        clusters = _greedy_clusters(answers, sim_threshold)
        largest = max(len(c) for c in clusters)
        if largest / samples_used >= stop_fraction:
            stopped_early = True

    # Batch 2: Overflow samples if early stop did not fire
    if not stopped_early and samples_used < max_samples and len(answers) == min_samples:
        remaining_indices = list(range(min_samples, max_samples))
        with ThreadPoolExecutor(max_workers=max(1, len(remaining_indices))) as pool:
            results = list(pool.map(_sample_single, remaining_indices))
            for res in results:
                if res is not None:
                    answers.append(res)
        samples_used = len(answers)

    clusters = _greedy_clusters(answers, sim_threshold)
    best_cluster: list[int] = []
    best_weight = -1.0
    for cl in clusters:
        weight = sum(answers[i]["faithfulness"] for i in cl)
        if weight > best_weight:
            best_weight, best_cluster = weight, cl

    winner = max(best_cluster, key=lambda i: answers[i]["faithfulness"])
    result = answers[winner]

    agreement = len(best_cluster) / samples_used
    faithfulness_mean = sum(a["faithfulness"] for a in answers) / len(answers)
    return {
        "answer": result["answer"],
        "model": result["model"],
        "samples_used": samples_used,
        "agreement": round(agreement, 3),
        "faithfulness_mean": round(faithfulness_mean, 3),
        "path_scores": [
            {
                "sample": i,
                "faithfulness": round(a["faithfulness"], 3),
                "cluster": next((ci for ci, c in enumerate(clusters) if i in c), -1),
                "temperature": round(a["temperature"], 2),
            }
            for i, a in enumerate(answers)
        ],
        "stopped_early": stopped_early,
        "duration_ms": int((time.monotonic() - t0) * 1000),
    }
