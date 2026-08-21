# Internal Fixture Pilot Report

> **Protocol smoke test—not a randomized controlled trial.** The baseline and treatment drafts are hand-authored fixtures bundled with the repository. This report validates scoring behavior; it does not estimate improvement for live models or real coding tasks.

**Execution timestamp:** `2026-08-21T18:57:36.077268+00:00`
**Evaluation split:** `all` (7 paired fixtures)
**Primary-endpoint interpretation:** **not significant at alpha=0.05**
**Internal verdict:** `INTERNAL_PILOT_DIRECTIONAL`

## Observed fixture results

| Metric | Baseline fixtures | Treatment fixtures | Observed difference / result | Interpretation |
|:---|---:|---:|---:|:---|
| All-constraint pass rate | 0.0% | 71.4% | +71.4 percentage points | Descriptive, n=7 |
| Exact McNemar primary test | — | — | p=0.0625 | not significant at alpha=0.05 |
| Wilcoxon score comparison | — | — | p=0.0180 | Exploratory secondary metric |
| Standardized score difference | — | — | d=2.996 | Large observed standardized difference; not independent proof of significance |
| Bootstrap interval for mean score difference | — | — | [0.486, 0.964] | Fixture uncertainty only; not population generalization |

## Paired fixture breakdown

| Case ID | Split | Slice | Display order swapped? | Baseline | Treatment | Score difference |
|:---|:---|:---|:---|:---|:---|---:|
| `follow_json_cap` | `dev` | `following` | No | Fail | Pass | +0.75 |
| `follow_bullets_no_secret` | `dev` | `following` | No | Fail | Fail | +0.25 |
| `follow_file_scope` | `dev` | `following` | Yes | Fail | Fail | +0.20 |
| `ground_quotes` | `dev` | `grounding` | No | Fail | Pass | +1.00 |
| `hold_direct_cap` | `holdout` | `following` | No | Fail | Pass | +1.00 |
| `hold_must_test` | `holdout` | `following` | No | Fail | Pass | +1.00 |
| `hold_ground` | `holdout` | `grounding` | No | Fail | Pass | +1.00 |

## Limitations

- Candidate drafts are hand-authored fixtures; no host model generated either arm under randomized assignment.
- Position assignment is randomized, but the deterministic constraint scorer does not inspect presentation order; this is not evaluator blinding.
- Seven cases are insufficient for broad model, repository, cost, safety, or product-effect claims.
- Exact quote occurrence checks do not prove source authority or full claim entailment.
- The exact McNemar test is the registered primary binary endpoint. Secondary score statistics do not override it.

## Appropriate use

Use this suite as a release smoke test for the evaluation protocol. A confirmatory product claim requires independently generated candidates, equal budgets, a frozen larger task set, pre-registration, and external replication.