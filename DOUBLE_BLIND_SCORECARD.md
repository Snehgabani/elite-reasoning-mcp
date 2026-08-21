# Internal Fixture Pilot Scorecard

**Version:** `2.9.0`
**Status:** `internal_pilot`
**Scope:** Seven bundled, hand-authored baseline/treatment draft pairs

> **This is a protocol smoke test, not a randomized controlled trial.** No live host model generated the candidate arms under randomized assignment. The observed results cannot establish broad model improvement, production reliability, cost reduction, or causal impact.

## Observed results

| Metric | Result | Interpretation |
|:---|---:|:---|
| Baseline all-constraint pass rate | 0/7 (0.0%) | Descriptive fixture result |
| Treatment all-constraint pass rate | 5/7 (71.4%) | Descriptive fixture result |
| Observed absolute difference | +71.4 percentage points | Not a population estimate |
| Exact McNemar p-value | 0.0625 | **Not significant at alpha=0.05** |
| Primary-endpoint verdict | `INTERNAL_PILOT_DIRECTIONAL` | Confirmatory claim not supported |

## What this pilot establishes

- The paired-fixture runner executes.
- The deterministic constraint scorer distinguishes the bundled drafts.
- The exact paired binary test is calculated and reported.
- Release automation can detect changes in the fixture protocol.

## What this pilot does not establish

- That Elite improves a live model's output.
- That benefits generalize across models, tasks, repositories, or users.
- That the workflow reduces cost, latency, vulnerabilities, or syntax failures in production.
- That position assignment constitutes evaluator blinding; scoring is deterministic and the candidate drafts are prewritten.

A confirmatory claim requires independently generated candidate arms, equal budgets, a frozen larger task set, pre-registration, and external replication. See [`docs/product_hardening_implementation_plan.md`](docs/product_hardening_implementation_plan.md) for the implementation and evaluation roadmap.
