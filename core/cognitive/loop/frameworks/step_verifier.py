"""PRM-style Step Verification — v15 P0 #2.

Research base:
- GenPRM: Scaling Test-Time Compute of Process Reward Models via Generative
  Reasoning (arXiv:2504.00891) — generative (not scalar) judgment for EACH
  reasoning step, with explicit reasoning before the verdict.
- Inference-Time Scaling for Generalist Reward Modeling / DeepSeek-GRM
  (arXiv:2504.02495) — pointwise generative reward modeling; parallel sampling
  and a meta-verifier to aggregate judgments.
- PAG: Policy as Generative Verifier (arXiv:2506.10406) — verify-then-revise
  workflows improve both reasoning and verification.

This module implements a lightweight generative step-critic: the final answer
is split into claim-steps, each step is verified by a targeted LLM query that
must reason briefly and then emit a verdict, and the judgments are aggregated.
It is NOT a trained PRM — it is the generative self-verification pattern the
papers above show scales at test time. Honest limits are documented in the
module docstring and surfaced in `warnings`.

Fail-open: if the LLM is unavailable, verification returns None — the answer
is never blocked, exactly like the v14/v15 synthesis fallback.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from typing import Any, Callable, Optional

_LLM_PROXY_URL = "http://127.0.0.1:4096/v1/chat/completions"
_LLM_MODEL = "gpt-oss:20b"

_VERDICT_RE = re.compile(r"(PASS|FAIL)", re.IGNORECASE)
_SCORE_RE = re.compile(r"(?:SCORE|score)[:\s]*([0-9]*\.?[0-9]+)")
_REASON_RE = re.compile(r"(?:REASON|reason)[:\s]*(.+)", re.IGNORECASE)

# Step-splitting: numbered lists ("1.", "1)", "1:"), bullets, or sentences.
_STEP_SPLIT_RE = re.compile(
    r"\n\s*(?:\d+[.)]\s+|\d+:\s+|[-*•]\s+)|\n(?=[A-Z][a-z]+[^.!?]{20,}[.!?])"
)


def _default_llm_call(prompt: str, temperature: float = 0.2) -> tuple[str, str]:
    """Call the local LLM proxy (same lane as synthesis: gpt-oss:20b)."""
    body = json.dumps(
        {
            "model": _LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": 512,
        }
    ).encode()
    req = urllib.request.Request(
        _LLM_PROXY_URL, data=body, headers={"Content-Type": "application/json"}
    )
    last_err: Exception | None = None
    for _ in range(2):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            msg = data["choices"][0]["message"]
            text = (msg.get("content") or "").strip()
            if not text:
                text = (msg.get("reasoning") or "").strip()
            if text:
                return text, _LLM_MODEL
            last_err = RuntimeError("empty completion")
        except Exception as e:  # noqa: BLE001
            last_err = e
    if last_err is not None:
        raise last_err
    return "", ""


def split_steps(answer: str, max_steps: int = 3) -> list[str]:
    """Split the final answer into claim-steps for per-step verification.

    Prefers numbered/bulleted lines; falls back to sentence splitting.
    Capped at max_steps to bound verification latency (each step = 1 LLM call).
    """
    if not answer:
        return []
    lines = [
        ln.strip() for ln in _STEP_SPLIT_RE.split(answer) if ln.strip()
    ]
    if len(lines) >= 2:
        steps = lines
    else:
        steps = [s.strip() + "." for s in re.split(r"(?<=[.!?])\s+", answer) if s.strip()]
    return steps[:max_steps]


def _parse_verdict(text: str) -> dict[str, Any]:
    """Tolerant extraction of SCORE / VERDICT / REASON from verifier prose."""
    m = _VERDICT_RE.search(text)
    verdict = "PASS" if (m and m.group(1).upper() == "PASS") else "FAIL"
    score_m = _SCORE_RE.search(text)
    score = float(score_m.group(1)) if score_m else (1.0 if verdict == "PASS" else 0.0)
    reason_m = _REASON_RE.search(text)
    reason = (reason_m.group(1).strip() if reason_m else text.strip())[:200]
    return {
        "verdict": verdict,
        "score": max(0.0, min(1.0, score)),
        "reason": reason,
    }


from concurrent.futures import ThreadPoolExecutor, as_completed

def verify_steps(
    prompt: str,
    answer: str,
    subproblems: list[dict[str, Any]] | None = None,
    llm_call: Callable[[str, float], tuple[str, str]] | None = None,
    max_steps: int = 3,
    pass_threshold: float = 0.7,
) -> dict[str, Any]:
    """Verify the answer's claim-steps with a generative step-critic in parallel.

    Args:
        prompt: original user task.
        answer: synthesized final answer (from reasoning_run).
        subproblems: pipeline decomposition, injected as context so the critic
            checks steps against the task decomposition.
        llm_call: injectable (prompt, temperature) -> (text, model); tests
            script this. Defaults to the local proxy.
        max_steps: cap on verified steps (latency bound).
        pass_threshold: mean score required for verified=True.

    Returns dict: steps (per-step verdicts), verification_score (mean, or None),
    verified (bool or None), model, duration_ms. On LLM failure returns
    score=None / verified=None (fail-open; answer never blocked).
    """
    steps = split_steps(answer, max_steps=max_steps)
    if not steps:
        return {
            "steps": [], "verification_score": None, "verified": None,
            "model": "", "duration_ms": 0,
        }
    call = llm_call or _default_llm_call
    sub_ctx = ""
    if subproblems:
        names = "; ".join(
            s.get("name", "") or s.get("index", "") for s in subproblems
        ) or "none"
        sub_ctx = f"\nTask decomposition: {names}."

    t0 = time.monotonic()

    def _verify_single(idx: int, step_text: str) -> tuple[int, dict[str, Any], str]:
        check = (
            "You are a step-level critic. Verify ONE reasoning step of an "
            "answer. Reason briefly about whether the step is correct, follows "
            "from the task and the preceding context, and is free of obvious "
            "errors. Then emit exactly:\n"
            "VERDICT: PASS or FAIL\nSCORE: 0.0 to 1.0\nREASON: one sentence\n\n"
            f"TASK: {prompt}{sub_ctx}\n\n"
            f"STEP {idx}/{len(steps)} TO VERIFY: {step_text}\n\nVERDICT:"
        )
        text, model_name = call(check, 0.2)
        parsed = _parse_verdict(text)
        parsed["step"] = step_text
        return idx, parsed, model_name

    step_verdicts: list[dict[str, Any]] = [None] * len(steps)
    model = ""
    llm_failed = False

    with ThreadPoolExecutor(max_workers=max(1, len(steps))) as executor:
        futures = {executor.submit(_verify_single, i + 1, step): i for i, step in enumerate(steps)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                _, parsed, model_name = future.result()
                step_verdicts[idx] = parsed
                if model_name:
                    model = model_name
            except Exception:
                llm_failed = True

    if llm_failed or any(v is None for v in step_verdicts):
        return {
            "steps": [], "verification_score": None, "verified": None,
            "model": "", "duration_ms": int((time.monotonic() - t0) * 1000),
        }
    score = sum(v["score"] for v in step_verdicts) / len(step_verdicts)
    return {
        "steps": step_verdicts,
        "verification_score": round(score, 3),
        "verified": bool(score >= pass_threshold),
        "model": model,
        "duration_ms": int((time.monotonic() - t0) * 1000),
    }
