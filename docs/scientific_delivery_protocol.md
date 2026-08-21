# Scientific Delivery Protocol: OODAA Quality Loops

**Purpose:** Improve Elite Reasoning MCP through falsifiable, evidence-producing iterations rather than feature accumulation or self-assigned quality scores.

OODAA means **Observe → Orient → Decide → Act → Assess**. The final assessment is deliberately separate from action: implementation success is not evidence that the intended outcome improved.

## 1. Required cycle record

Every material product iteration must record:

```yaml
cycle_id: unique immutable ID
problem: observable failure, not a proposed feature
population: users, tasks, code paths, or environments in scope
baseline:
  metric: definition
  value: observed value
  sample_size: n
hypothesis: falsifiable expected change
intervention: smallest change capable of testing the hypothesis
primary_endpoint: one preselected metric
secondary_endpoints: limited supporting metrics
harm_endpoints: safety, privacy, latency, cost, false positives
acceptance_rule: fixed before implementation
rollback_rule: fixed before implementation
results: filled only after action
verdict: adopt | revise | reject | insufficient_evidence
```

A cycle without a measured baseline is engineering exploration, not a product experiment. It may still proceed, but it must be labeled exploratory.

## 2. The OODAA loop

### Observe

Collect facts before choosing a solution:

- reproduce the failure;
- identify the affected path and population;
- capture current tests, latency, imports, dependencies, and failure frequency;
- distinguish user reports from assumptions;
- record missing information as `UNKNOWN`;
- avoid changing implementation during observation.

Required output: a versioned baseline artifact or a reproducible failing test.

### Orient

Build competing explanations:

- map trust boundaries and dependencies;
- identify whether the failure is product, protocol, environment, or documentation;
- list at least one simpler alternative;
- identify confounders and measurement error;
- determine whether deterministic evidence is available;
- state the expected mechanism of improvement.

Required output: a short causal model, explicit assumptions, and risks.

### Decide

Pre-register the smallest useful experiment:

- select one primary endpoint;
- set the minimum practical improvement;
- set safety/non-inferiority limits;
- define sample size or explain why the cycle is exploratory;
- freeze acceptance and rollback rules;
- choose the minimum intervention;
- assign an owner and time bound.

Required output: an immutable cycle manifest before production code changes.

### Act

Implement without moving the goalposts:

- add a failing characterization test first where possible;
- separate code movement from behavior changes;
- keep compatibility and migration paths explicit;
- capture commands and artifact digests;
- do not edit the primary metric or acceptance threshold;
- record deviations from the manifest.

Required output: reviewable patch, tests, migration notes, and exact validation commands.

### Assess

Evaluate independently of implementation intent:

- rerun the baseline and intervention under matched conditions;
- inspect primary, secondary, and harm endpoints;
- report negative and null results;
- classify uncertainty and missing evidence;
- check whether evidence still matches the current code/repository digest;
- adopt, revise, reject, or request more evidence.

Required output: signed-off verdict and the next observation, not an automatic success claim.

## 3. Statistical rules

1. Choose the primary endpoint before observing treatment results.
2. Use paired analysis for matched tasks.
3. Report effect size and uncertainty; do not report only p-values.
4. Do not allow a significant secondary metric to override a failed primary endpoint.
5. Correct for multiple secondary comparisons.
6. Keep development and confirmatory sets separate.
7. Use temporal or repository splits to reduce contamination.
8. Treat internally authored fixtures as protocol tests, not population evidence.
9. Publish exclusions, errors, ties, and missing outcomes.
10. Replicate consequential results on a fresh slice and, eventually, externally.

## 4. Engineering evidence hierarchy

From strongest to weakest for a specific claim:

1. Independent production outcome or hidden-task oracle.
2. Reproduced end-to-end installed-artifact test.
3. Integration test through the public MCP protocol.
4. Deterministic unit/property/mutation test.
5. Static inspection or type check.
6. Internal score or heuristic.
7. Implementation intent or prose assertion.

A lower level cannot be used to claim a higher-level outcome. For example, AST parsing cannot prove absence of vulnerabilities, and a passing mocked fixture cannot prove improved model performance.

## 5. Product-level nested loops

### Per pull request

- Observe: failing test or baseline.
- Orient: root cause and alternatives.
- Decide: PR acceptance criteria.
- Act: minimal patch.
- Assess: targeted tests, full suite, lint/types, and regression review.

### Per release

- Observe: reliability, upgrade, and user-friction data.
- Orient: release risk and affected cohorts.
- Decide: release gates and rollback conditions.
- Act: build the immutable artifact.
- Assess: clean-wheel matrix, schema migrations, MCP session, and canary usage.

### Per benchmark

- Observe: frozen baseline arms.
- Orient: task/model strata and confounders.
- Decide: preregistered protocol and power.
- Act: execute blinded matched candidates.
- Assess: locked analysis, harms, limitations, and replication.

### Per product quarter

- Observe: activation, retention, useful detections, false positives, and disabling.
- Orient: user segment and failure taxonomy.
- Decide: one product bet and stop/go metric.
- Act: ship to a bounded design-partner cohort.
- Assess: retain, revise, narrow, or stop.

## 6. Current hardening-cycle examples

### Cycle CORE-001 — Claims integrity

- Observation: README claims disagreed with repository artifacts.
- Hypothesis: a registry-generated claim block will eliminate numeric drift.
- Primary endpoint: CI rejects every seeded mismatch.
- Harm endpoint: release checks remain dependency-light.
- Intervention: JSON-compatible YAML registry and standard-library validator.
- Result: adopted; mismatch, expiry, artifact, and forbidden-language tests pass.

### Cycle CORE-002 — Unsupported completion

- Observation: a draft saying “pytest passed” could satisfy a draft-level constraint.
- Hypothesis: independently executed test evidence bound to repository state will reject prose-only and stale completion.
- Primary endpoint: prose-only and post-test mutation fixtures return `REPEAT`; current executed evidence returns `DONE`.
- Harm endpoint: raw source content is not persisted in evidence.
- Intervention: four-state evidence records, workflow evidence store, restricted command runner, and Git snapshot digest.
- Result: adopted; all three state transitions are covered through the public gateway.

### Cycle CORE-003 — Core startup sprawl

- Observation: the core profile imported and registered the legacy cognitive catalog before deleting it.
- Hypothesis: direct core registration and lazy compatibility exports remove graph imports without breaking public behavior.
- Primary endpoint: subprocess core startup and syntax checks do not import LangGraph/global cognitive engine.
- Harm endpoint: legacy profile compatibility suite remains passing.
- Intervention: direct gateway registration and lazy `core.cognitive` exports.
- Result: adopted; subprocess import-boundary and legacy-surface tests pass.

### Cycle CORE-004 — Verification dispatcher maintainability

- Observation: verification semantics were embedded in a growing gateway conditional.
- Hypothesis: typed registry handlers reduce gateway coupling while preserving all public results.
- Primary endpoint: every public verification check passes the same integration tests through registry dispatch.
- Harm endpoint: output schema and five-tool discovery remain unchanged.
- Intervention: typed registry, restricted command adapter, and separate API schemas.
- Status: assessment in progress.

## 7. Stop conditions

Stop or revise an intervention when:

- the primary endpoint fails;
- a critical privacy or safety endpoint regresses;
- equivalent static prompting performs as well with less friction;
- false positives cause meaningful workflow abandonment;
- maintenance cost exceeds measured user value;
- evidence is stale, contaminated, or underpowered;
- implementation requires changing the pre-registered success rule.

The default scientific verdict is not “success.” It is **insufficient evidence** until the acceptance rule is met.
