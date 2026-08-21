# Quality Improvement and Double-Blind Evaluation Plan
**Status:** proposed roadmap, not a claim that the current scorecard proves the effect

## Executive assessment
This is a promising project with a high-leverage thesis: put a small, cheap model inside a deterministic workflow that makes requirements explicit, retrieves evidence, and blocks unsafe or unverified completion. The strongest product idea is not “make a model reason harder”; it is **make a weak model fail cheaply, visibly, and recoverably**.

The repository already has useful primitives: a compact five-tool core surface, task contracts, quote-oriented grounding, workflow progress, persistent memory, syntax/security checks, and a test suite for position swapping and McNemar-style decisions. That is a good foundation for a reliability product.

However, the current public claims and `DOUBLE_BLIND_SCORECARD.md` should be treated as a prototype, not scientific evidence. Five hand-authored pairs cannot establish a +1,480 Elo or Cohen's d = 4.50 claim. In `scripts/double_blind_eval.py`, treatment scores are partly assigned by rule (`0.98` or `max(0.95, ...)`), control and treatment are not generated under a common randomized protocol, the two “passes” reuse the same scores rather than independently judging swapped presentations, and `exec` is not a security sandbox. Those issues are fixable and should be the first credibility milestone.

The realistic north-star is: **higher task success and groundedness per dollar, with no unacceptable safety or latency regression**, measured on fresh tasks and real deployment traces.

## MCP-assisted repository audit
I followed the repository's MCP workflow with `elite_prepare` and `elite_admin`. The server returned `budget_tier=research_grade`, required evidence before drafting, and exposed the compact core surface: `elite_prepare`, `elite_progress`, `elite_verify`, `elite_memory`, and `elite_admin`. Its explicit warning was that it cannot physically stop a host model from skipping tools. That is an important product boundary: protocol guidance is not enforcement unless the client honors it.

The MCP evidence call returned `degraded=true` with zero sources in this local environment. Therefore, the research claims below are based only on the independently performed web search links and are marked with direct source quotes; the degraded MCP retrieval must be fixed before calling the end-to-end research path production-ready.

## What to optimize: a measurable objective
Define a primary utility score before changing prompts or architecture:
```
U = (success × groundedness × safety × instruction_following) / (dollars + λ·latency + μ·human_review_minutes)
```
Use separate hard gates for safety and privacy; do not let a cheap but unsafe answer compensate for a security failure. Report the vector, not only U:
- **Outcome:** task success / pass@1, hidden-test pass rate, correct final state.
- **Grounding:** claim-level entailment, citation precision, citation recall, source diversity, stale-source rate.
- **Following:** exact constraint pass rate, schema validity, forbidden-action rate.
- **Reliability:** retry rate, escalation rate, tool-order adherence, recovery success, regression rate.
- **Efficiency:** model tokens, MCP calls, web requests, wall-clock latency, dollars per successful task.
- **Calibration:** Brier score and selective accuracy at abstention thresholds.
- **Human impact:** time-to-completion, edit distance to accepted answer, and blind user preference.

Pre-register one primary endpoint (for example, hidden-test task success per dollar) and a small number of secondary endpoints. Do not select the most favorable metric after looking at results.

## Improvement roadmap

### Phase 0 — Make claims and contracts honest (1 week)
1. Replace absolute README language such as “zero vulnerabilities,” “frontier-level,” and “+1,480 Elo” with measured, versioned, confidence-interval-backed language.
2. Add a `claims.yml` registry: claim, evidence source, dataset version, run ID, confidence interval, expiry, and owner.
3. Make `elite_prepare` produce a typed contract with: goal, non-goals, allowed tools, evidence requirements, budget, stop conditions, and abstention conditions.
4. Add a strict “unknown / not retrieved” state. A failed search must never become a plausible citation.
5. Treat the current five-item result as a smoke fixture only; label it `demo`, never `RCT`.

### Phase 1 — Improve the cheap-model interface (1–2 weeks)
1. **Small structured outputs:** use short JSON contracts and enumerated states (`NEED_EVIDENCE`, `DRAFT`, `REVISE`, `ESCALATE`, `DONE`). Validate with Pydantic and return concise error repair instructions.
2. **Progressive disclosure:** expose the five core tools by default; reveal legacy tools only when the contract requires them. This is already directionally correct.
3. **One-shot task decomposition:** compile a maximum of 3–7 independently checkable subtasks. Avoid asking the small model to emit long chain-of-thought; store only decisions, evidence, and concise rationales.
4. **Verifier-first generation:** require the model to state expected tests and evidence before it writes. Run deterministic checks before any prose polish.
5. **Bounded recovery:** at most two targeted repair loops, then escalate. Log the failure category so retries do not repeat the same bad strategy.
6. **Format repair:** parse, validate, and automatically request only the missing field rather than replaying the whole prompt.
7. **Cost router:** use cheap path for low-risk deterministic tasks, research path for factual/current questions, and human/frontier escalation for high-impact or ambiguous actions.

### Phase 2 — Build trustworthy web research (2–4 weeks)
1. Search at least two independent sources when the claim matters; prefer primary documents, official documentation, standards, and peer-reviewed proceedings.
2. Preserve URL, title, retrieval timestamp, publication date, exact quote, and the claim it supports.
3. Compute claim-level citation precision: every cited quote must occur verbatim in fetched text. Compute citation recall: every material factual claim must have support.
4. Add contradiction handling: if sources disagree, show the disagreement and lower confidence; never average incompatible facts.
5. Add temporal policy: current facts require a retrieval timestamp and a maximum age; historic facts require publication date.
6. Add source-quality and independence labels. Two syndicated copies are not two independent sources.
7. Use perspective diversity as a retrieval strategy, not as proof of truth. STORM's own paper reports source-bias transfer and fabricated connections as limitations.
8. Test prompt-injection resistance in pages: quoted web text is untrusted data, never an instruction to the agent.

### Phase 3 — Safety and execution integrity (2–4 weeks)
1. Replace in-process `exec` evaluation with disposable containers or a strongly restricted subprocess: no network, read-only base image, non-root user, CPU/memory/time limits, syscall/profile restrictions, and a temporary filesystem.
2. Separate static policy checks from runtime tests. A passing AST check is not evidence that behavior is safe.
3. Test negative cases: prompt injection, malicious URLs, unsafe shell commands, path traversal, secrets in memory, poisoned memories, and partial writes.
4. Make HMAC authorization cover the exact base hash, patch, target path, actor, and expiration; reject replay and TOCTOU changes.
5. Make destructive actions require explicit user confirmation and an auditable intent record.
6. Add property-based and mutation tests to ensure the gates catch realistic bypasses, not only fixture examples.

### Phase 4 — Memory and learning without poisoning (ongoing)
1. Store compact lessons, not raw private prompts by default.
2. Keep source, scope, confidence, trust, expiry, and provenance on every memory.
3. Quarantine low-trust or sensitive memories; never silently promote them from retrieval similarity alone.
4. Measure memory utility with a held-out replay set: helpful retrieval rate, harmful retrieval rate, stale retrieval rate, and duplicate-token cost.
5. Add deletion, retention, export, and per-project isolation tests.
6. Feed only verified failures into anti-pattern memory; otherwise the system can learn the model's hallucination.

### Phase 5 — Observability and product metrics (ongoing)
Create a run-level event schema with hashed run ID, model/version, prompt template version, tool calls, evidence IDs, tokens, latency, outcomes, failures, and escalation. Do not export raw prompts or sensitive content by default. Build dashboards for:
- success per dollar by task family;
- grounding and abstention rate;
- failure taxonomy and recovery rate;
- tool selection and contract adherence;
- p50/p95 latency and web failure rate;
- regression versus a frozen baseline;
- subgroup/task-difficulty performance.

## The corrected double-blind study

### Hypotheses
Pre-register:
- **H1 primary:** treatment has higher hidden-test task success than baseline at equal task budget.
- **H2:** treatment has higher claim-level groundedness and lower unsupported-claim rate.
- **H3:** treatment has better exact instruction-following with no increase in unsafe-action rate.
- **H4 efficiency:** treatment has lower cost per successful task, even if raw token count is higher.
- **H5 usability:** treatment reduces human correction time.
Also pre-register harm hypotheses: more latency, over-refusal, citation laundering, prompt leakage, and false confidence.

### Arms and randomization
Use a 2×2 factorial design where possible:
- baseline small model, no scaffold;
- small model + MCP scaffold;
- small model + retrieval only;
- small model + deterministic gates only.
Keep model, temperature, maximum output, tools, time budget, and initial context fixed within a block. Randomize task order and treatment assignment using a cryptographically secure seed recorded before generation. Generate both arms independently for the same task; do not write a “treatment answer” by hand.

Use a fresh, hidden test set. Maintain a public development set and a locked test set. Add post-cutoff and newly collected tasks, paraphrases, adversarial variants, and cross-domain tasks. Static coding benchmarks are not sufficient: recent work explicitly warns that SWE-bench-style sets can contain memorized solutions and recommends contamination-resistant, continuously updated tasks [1](https://arxiv.org/html/2505.23419v2) [2](https://dl.acm.org/doi/10.1145/3786583.3786882).

### Blinding
1. A data steward assigns opaque IDs and removes model/provider names, tool names, formatting signatures, and metadata.
2. A separate runner executes candidates in matched environments.
3. Human raters see only task plus candidate A/B, with randomized order.
4. The analysis script unmasks only after the scoring lock and primary analysis are complete.
5. The treatment label remains hidden from judge models, human raters, and the analyst.

Blinding the evaluator is more important than hashing text. A deterministic hash is not randomization; it is reproducible ordering and can correlate with output properties.

### Objective scoring before subjective scoring
Use the strongest available oracle for each task:
- code: hidden tests, static analysis, security tests, patch applicability, regression tests;
- math: exact answer plus independently verified proof rubric;
- schema: parser and exact key/type/constraint checks;
- research: claim decomposition, source retrieval, quote occurrence, entailment, contradiction, and freshness;
- agent workflow: final state, side effects, recovery, and user time.

Use LLM judges only for residual qualities such as clarity or usefulness. They must not be the sole judge of factual correctness or code safety.

### Human-rating protocol
Sample enough tasks to estimate the smallest useful effect, with clustering by task and rater. Use two or more trained raters per subjective item, a written rubric, calibration examples, and an adjudication process. Report inter-rater agreement (Cohen's kappa or Krippendorff's alpha) and disagreements. Keep raters blind to arm, model family, and output length where possible.

For pairwise LLM judging, run A/B and B/A with fresh randomization, relabel the second result, and declare an order-dependent disagreement a tie or send it to human adjudication. This is supported by the LLM-as-a-judge literature, which identifies position bias and evaluates swapping as a mitigation [3](https://arxiv.org/html/2411.15594v6). Also audit verbosity, self-preference, formatting, and refusal bias; swapping alone does not remove them.

### Statistics
For paired binary outcomes, make a 2×2 table:
- `b`: baseline passes, treatment fails;
- `c`: baseline fails, treatment passes.
Use exact McNemar's test for the paired treatment effect. Report `c - b`, paired risk difference, odds ratio with a confidence interval, and a pre-registered decision rule. For continuous paired scores, use the mean paired difference with a bootstrap 95% CI or a mixed-effects model; do not use independent-sample Cohen's d as the only statistic. For ordinal ratings, use a mixed-effects ordinal model or a paired nonparametric analysis. For pairwise wins across heterogeneous tasks, fit a Bradley–Terry model with task and judge random effects; do not convert five wins into a fake Elo claim.

Use hierarchical models or cluster-robust intervals when multiple outcomes come from the same task, model, or rater. Correct for multiple secondary endpoints. Report all exclusions, missingness, ties, and early stopping. Publish the analysis code and a signed, immutable manifest of prompts, versions, seeds, and outputs after the study.

### Sample-size starting point
Do not choose `n=5`. For a paired binary outcome, power the study from the discordant-pair rate and the minimum practically important improvement. As a planning example only, detecting a change from 0.60 to 0.70 at 80% power and two-sided α=0.05 may require roughly 250–400 paired tasks depending on correlation and discordance. Run a simulation with the actual expected `b` and `c` rates, then lock the number. For subjective outcomes, inflate for rater/task clustering. A pilot should estimate variance; it should not be presented as confirmatory evidence.

### Acceptance gates
Ship an improvement only if all pre-registered conditions hold:
- primary success difference exceeds the minimum practical effect and its CI excludes zero;
- no statistically or practically meaningful increase in unsafe actions, unsupported citations, privacy leaks, or severe regressions;
- cost per successful task improves or is within an explicitly approved budget;
- worst task family does not regress beyond the pre-set margin;
- calibration and abstention improve or remain within bounds;
- results replicate on a fresh hidden slice and in a small real-user pilot.

## References used
- [1](https://arxiv.org/html/2505.23419v2): SWE-bench Live describes static-benchmark staleness and a continuously updated, contamination-resistant setup.
- [2](https://dl.acm.org/doi/10.1145/3786583.3786882): *The SWE-Bench Illusion* reports evidence consistent with memorization and argues for temporal/cross-repository controls.
- [3](https://arxiv.org/html/2411.15594v6): Survey of LLM-as-a-judge biases and position-swapping mitigation.
- [4](https://aclanthology.org/2024.naacl-long.347/): STORM paper. Its abstract reports a 25% absolute organization increase and 10% coverage increase versus an outline-driven RAG baseline, while the paper also reports source-bias and unrelated-fact risks.
- [5](https://www.rand.org/pubs/working_papers/WRA4869-1.html): RAND 2026 report on practical methodological challenges in human-AI RCTs, including standardized task libraries and versioned evaluation infrastructure.
- [6](https://metr.org/blog/2024-11-22-evaluating-r-d-capabilities-of-llms/): METR RE-Bench emphasizes novel, non-contaminated tasks and faithful human comparisons.
