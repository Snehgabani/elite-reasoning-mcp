# Elite Reasoning MCP: Product Hardening and Validation Implementation Plan

**Status:** Proposed execution plan  
**Planning horizon:** 12 months, with a 90-day credibility and core-product milestone  
**Primary objective:** Turn the existing functional MCP prototype into the most credible local contract, evidence, and trusted-memory control plane for coding agents.  
**Product boundary:** Elite compiles checkable contracts, gathers or accepts evidence, verifies completion claims, and stores trusted lessons. It does not claim to improve a model's latent intelligence or guarantee software correctness.

**Delivery method:** Every material milestone follows the [OODAA Scientific Delivery Protocol](scientific_delivery_protocol.md): Observe, Orient, Decide, Act, Assess.

---

## Implementation progress

Last updated: 2026-08-22

- [x] Add a machine-validated claims registry and generated README evidence block.
- [x] Correct pilot/RCT wording and primary-endpoint significance handling.
- [x] Add source spans, explicit/inferred provenance, verifier hints, and confidence to task constraints.
- [x] Add four-state verification results and content-addressed evidence bound to subject digests.
- [x] Stop the core profile from loading the legacy cognitive catalog during startup.
- [x] Make deterministic cognitive exports lazy so syntax checks do not load the graph engine.
- [x] Require independently executed, repository-bound test evidence before tested code workflows can return `DONE`.
- [x] Add a Git working-tree scope verifier with stale-state detection and dependency-manifest policy.
- [x] Replace gateway verification branching with a typed, inspectable verifier registry.
- [x] Move public response schemas and restricted command execution out of the gateway.
- [x] Give the core profile a dedicated finalization path that skips every legacy tool and resource registration block.
- [ ] Extract legacy composition from `mcp_server.py` and finish reducing the remaining server module.
- [x] Add explicit schema v7, integrity-checked migration backup, bounded retention, rollback, and doctor diagnostics.
- [ ] Decompose the remaining monolithic persistence repositories.
- [x] Move graph/model/sync/scientific dependencies behind `legacy` and add an isolated minimal-wheel core smoke gate.
- [ ] Land isolated installed-wheel validation on Linux, macOS, and Windows for Python 3.11 and 3.13 (implementation prepared; GitHub App lacks workflow-write permission).
- [x] Build a manifest-driven five-arm analysis harness and 250-task frozen corpus that reports `NOT_RUN` until independent matched outcomes are supplied.
- [x] Add an offline installed-product demo with a deterministic fail-then-pass verification transition.
- [x] Add previewable, confirmation-gated atomic IDE initialization and redacted workflow-evidence export.
- [x] Add continuous checkpoint directives, `/goal`, durable context recovery, host rules, continuity metrics, and real-gateway amnesia simulations.
- [ ] Complete adversarial security, memory-poisoning, and corruption suites.
- [ ] Run the design-partner and external-replication program.

## 1. Executive decision

The project should stop expanding its catalog of reasoning methods and concentrate engineering effort on three production capabilities:

1. **Contract compiler** — convert a user request into source-linked, machine-checkable requirements.
2. **Evidence-backed completion gate** — classify every expected outcome as `PASS`, `FAIL`, `UNKNOWN`, or `NOT_CHECKED` using suitable evidence.
3. **Trusted local memory** — retain compact, scoped, provenance-rich lessons without silently learning unverified or sensitive content.

Everything else must be classified as one of:

- **Core:** required by the default five-tool workflow.
- **Optional:** a separately installed adapter or verifier.
- **Experimental:** excluded from the default runtime and release claims.
- **Legacy:** compatibility-only, with a published removal policy.
- **Remove:** duplicate, incomplete, or unsupported implementation.

The first 90 days prioritize trust, architecture, and reproducible evidence. Market expansion begins only after the core artifact is small, reliable, measurable, and honest.

---

## 2. Measurable outcome model

### 2.1 North-star metric

**Verified successful workflows per active user per week**, where a verified workflow has:

- a contract tied to source instructions;
- a host-produced result;
- required evidence attached;
- all critical outcomes in `PASS`, or an explicit user-approved waiver;
- no unresolved critical `UNKNOWN` result;
- no privacy or scope violation.

This metric prevents optimizing for installations, tool calls, or generated plans that produce no user value.

### 2.2 Product quality scorecard

| Dimension | 90-day gate | 6-month gate | 12-month target |
|---|---:|---:|---:|
| Clean-install success | >= 98% in CI matrix | >= 98% in design-partner telemetry | >= 99.5% |
| MCP startup success | >= 99.5% automated | >= 99.5% observed | >= 99.9% |
| Core tool-call reliability | >= 99.5% | >= 99.7% | >= 99.9% |
| Contract explicit-requirement recall | >= 90% on frozen set | >= 93% | >= 95% |
| Critical invented-requirement rate | < 2% | < 1% | < 0.5% |
| False `PASS` rate for deterministic verifiers | < 1% | < 0.5% | < 0.1% |
| Unsupported completion reduction | measurable pilot | >= 20% relative | independently replicated |
| Scope-violation reduction | measurable pilot | >= 20% relative | independently replicated |
| p95 core verification latency | < 25 ms excluding commands/network | < 15 ms | < 10 ms |
| Default startup time | < 2 s | < 1.5 s | < 1 s |
| Core branch coverage | >= 85% | >= 90% | >= 95% |
| Week-4 retained design partners | baseline established | >= 35% | >= 45% |
| Severe privacy/security escapes | 0 | 0 | 0 |

### 2.3 Non-goals

Do not optimize for:

- number of MCP tools;
- number of named reasoning frameworks;
- internally generated “quality scores” without calibrated meaning;
- GitHub stars as the primary adoption metric;
- benchmark wins achieved by unequal token/tool budgets;
- forcing `elite_prepare` on trivial or low-risk tasks;
- replacing repository tests, code review, or human authorization.

---

## 3. Target architecture

### 3.1 Desired package layout

Migrate incrementally toward:

```text
core/
  api/                    # Five MCP tools, public request/response schemas
    server.py
    schemas.py
    errors.py
  contracts/              # Requirement extraction and typed task contracts
    models.py
    compiler.py
    extractors/
    policy.py
  verification/           # Evidence model, registry, built-in verifiers
    models.py
    registry.py
    orchestrator.py
    syntax.py
    constraints.py
    test_command.py
    git_diff.py
    grounding.py
  memory/                 # Trusted memory domain and repositories
    models.py
    service.py
    policy.py
    repository.py
  persistence/            # SQLite connection, migrations, transactions
    database.py
    migrations/
    repositories/
  policy/                 # Risk, privacy, retention, routing
    risk.py
    privacy.py
    routing.py
  telemetry/              # Local event schema and aggregate metrics
    events.py
    recorder.py
    reports.py
  plugins/                # Stable verifier SDK and discovery
    protocol.py
    loader.py
  adapters/               # IDE, MCP transport, optional web adapters
  experimental/           # Never imported by core; excluded from wheel by default
```

This is a destination, not a one-PR rewrite. Existing imports remain behind compatibility facades during migration.

### 3.2 Runtime dependency rule

The default five-tool server may depend only inward:

```text
api -> contracts, verification, memory, policy, telemetry
verification -> contracts, policy
memory -> persistence, policy
telemetry -> persistence, policy
contracts -> domain models only
```

The core runtime must never import `core.cognitive`, `core.eval`, legacy tool modules, LangGraph, model-provider clients, or research frameworks during default startup.

Add an architectural test that fails when forbidden imports cross these boundaries.

### 3.3 Distribution strategy

Retain one project initially, but split dependencies into extras:

- Default: MCP transport, Pydantic, SQLite-based core.
- `[web]`: HTTP retrieval and HTML parsing.
- `[vectors]`: vector memory dependencies.
- `[legacy]`: legacy broad tool surface.
- `[experimental]`: cognitive/research graph dependencies.
- `[dev]`: tests, typing, mutation and security tools.

After adoption and API stability, evaluate separate distributions. Do not split packages before import boundaries are proven.

### 3.4 Public compatibility policy

- Keep five public MCP tool names through the next major version.
- Version structured payloads with `schema_version`.
- Add fields compatibly; do not silently change semantics.
- Provide at least one minor-release deprecation window.
- Persisted database changes require forward migrations and tested backup/restore.
- `legacy` receives security fixes only after the core architecture milestone.

---

## 4. Workstreams

## WS1 — Claims integrity and public trust

**Owner profile:** Product lead + benchmark lead  
**Priority:** P0  
**Starts:** Day 1

### Objectives

Make every public claim consistent, reproducible, scoped, and automatically checked.

### Implementation tasks

1. Extend `claims.yml` schema with:
   - `statement`;
   - `scope` and exclusions;
   - `metric_definition`;
   - dataset and code versions;
   - run ID and immutable artifact digest;
   - sample size;
   - point estimate and uncertainty;
   - replication status;
   - expiry date;
   - owner;
   - permitted public wording.
2. Add `scripts/validate_claims.py` to:
   - validate required fields;
   - verify referenced artifacts exist;
   - reject expired production claims;
   - compare README numeric claims against registry values;
   - reject forbidden absolute phrases unless explicitly approved in registry.
3. Replace unsupported README claims with pilot wording.
4. Correct the McNemar interpretation: `p=0.0625` is not significant at `p<0.05`.
5. Rename the seven-case benchmark to an **internal pilot** in generated reports.
6. Generate the README benchmark table from `claims.yml`; do not duplicate numbers manually.
7. Add a “Guarantees and limitations” section distinguishing:
   - deterministic checks;
   - environmental checks;
   - heuristic extraction;
   - unknown/unverified claims;
   - host compliance limitations.
8. Run claims validation in PR CI and release CI.

### Files affected

- `claims.yml`
- `README.md`
- `BENCHMARK_REPORT.md`
- `DOUBLE_BLIND_SCORECARD.md`
- `scripts/validate_claims.py` (new)
- `scripts/double_blind_eval.py`
- `scripts/release_check.py`
- `tests/test_claims_registry.py` (new)

### Acceptance criteria

- No numeric product-performance claim appears outside the registry-generated block.
- Every public empirical claim links to a command and immutable result artifact.
- CI fails on a mismatched, expired, or unsupported claim.
- Pilot reports clearly state sample size and limitations.

---

## WS2 — Typed contract compiler

**Owner profile:** Core engineer  
**Priority:** P0  
**Starts:** Week 2

### Objectives

Replace loosely parsed descriptions with traceable constraints that specify how they will be checked.

### Domain model

```python
class Requirement(BaseModel):
    id: str
    kind: RequirementKind
    source_text: str
    source_start: int
    source_end: int
    interpretation: str
    severity: Literal["critical", "required", "preference"]
    verifier: str | None
    verifier_parameters: dict[str, JsonValue]
    extraction_confidence: float
    status: Literal["proposed", "confirmed", "waived"]


class TaskContract(BaseModel):
    schema_version: str
    goal: str
    deliverable: str
    requirements: list[Requirement]
    non_goals: list[str]
    evidence_requirements: list[EvidenceRequirement]
    risk_tier: RiskTier
    stop_conditions: list[str]
    max_repair_attempts: int
```

### Requirement kinds for v1

- `required_content`
- `forbidden_content`
- `output_format`
- `word_limit`
- `allowed_files`
- `forbidden_files`
- `dependency_policy`
- `compatibility`
- `test_command`
- `security`
- `performance`
- `citation_grounding`
- `direct_answer`
- `human_approval`

### Implementation tasks

1. Introduce immutable Pydantic domain models under `core/contracts/`.
2. Preserve source spans for every extracted explicit requirement.
3. Split extraction into small deterministic extractors by kind.
4. Define precedence and conflict rules:
   - explicit user constraint beats inferred default;
   - critical conflicting requirements produce `needs_clarification`;
   - uncertain requirements remain `proposed`, never silently critical;
   - absent requirements are not invented.
5. Add contract normalization and stable IDs based on source location and normalized content.
6. Add a risk router that chooses among:
   - `SKIP_PREPARE`;
   - `CONTRACT_ONLY`;
   - `CONTRACT_AND_VERIFY`;
   - `STRICT_WITH_APPROVAL`.
7. Replace generic confidence with per-requirement extraction confidence.
8. Keep `core/reasoning/task_contract.py` as a facade while migrating callers.
9. Create a frozen corpus of at least 250 prompts with hand-labeled requirements.
10. Measure exact match, requirement recall, severity accuracy, and invented-requirement rate by requirement kind.
11. Add property tests for whitespace, punctuation, Unicode, repeated constraints, negation, and conflicting instructions.

### Files affected

- `core/contracts/*` (new)
- `core/reasoning/task_contract.py` (compatibility facade)
- `core/reasoning/nuclear_prompt.py` (remove from core path when replaced)
- `core/orchestration/workflow_run.py`
- `core/tools/gateway.py`
- `tests/contracts/*` (new)
- `evals/contracts/` (new fixtures and manifest)

### Acceptance criteria

- >=90% recall of explicit critical/required constraints on the frozen corpus.
- <2% critical invented-requirement rate.
- Every explicit requirement points to exact source text.
- Conflicts and ambiguity produce a typed clarification state.
- Existing five-tool contract tests pass through the compatibility facade.

---

## WS3 — Evidence model and verifier registry

**Owner profile:** Core/security engineer  
**Priority:** P0  
**Starts:** Week 3

### Objectives

Make completion status a product of typed evidence rather than generic scores or host assertions.

### Result model

```python
class VerificationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_CHECKED = "NOT_CHECKED"


class Evidence(BaseModel):
    id: str
    kind: str
    producer: str
    collected_at: datetime
    subject_digest: str
    payload: dict[str, JsonValue]
    redactions: list[str]
    artifact_digest: str


class VerificationResult(BaseModel):
    requirement_id: str
    verifier: str
    verifier_version: str
    status: VerificationStatus
    reason: str
    evidence_ids: list[str]
    limitations: list[str]
    duration_ms: float
```

### Built-in verifier set

1. **Constraint verifier:** format, length, required/forbidden terms.
2. **Python syntax verifier:** parser output with subject digest.
3. **Test-command verifier:** argv allowlist, explicit opt-in, cwd scope, timeout, exit code, bounded output.
4. **Git-diff verifier:** allowed files, forbidden files, dependency manifests, unexpected generated files.
5. **Grounding verifier:** URL, retrieval time, exact quote occurrence, source digest, freshness.
6. **Evidence completeness verifier:** required evidence exists and matches current subject digest.
7. **Human approval verifier:** explicit approval event bound to action digest and expiration.

### Implementation tasks

1. Create a verifier protocol and registry; remove branching dispatch from the gateway over time.
2. Require verifiers to declare supported requirement kinds and evidence kinds.
3. Bind evidence to a digest of the draft, diff, or command context to prevent stale evidence reuse.
4. Return `UNKNOWN` for environmental failures, inaccessible sources, missing tools, and unsupported languages.
5. Return `NOT_CHECKED` when no verifier was selected or execution was not authorized.
6. Never map “did not crash” to `PASS`.
7. Remove generic quality scores from completion decisions.
8. Add bounded repair policy: maximum two targeted repeats by default, then `BLOCKED` or escalation.
9. Add evidence bundle export/import with schema version and integrity digest.
10. Add mutation tests for constraint, diff, and grounding verifiers.
11. Add adversarial fixtures for stale output, altered draft after test, forged URLs, truncated logs, and command-prefix bypasses.

### Security requirements for commands

- No shell invocation.
- Parse with `shlex`, execute argv directly.
- Resolve executable against an explicit allowlist.
- Restrict cwd to an approved project root.
- Set timeout, output limit, and environment allowlist.
- Record return code and executable identity.
- Prefer future sandbox adapters; do not imply current subprocess isolation is a sandbox.

### Files affected

- `core/verification/*` (new)
- `core/reasoning/constraint_check.py` (facade/migrate)
- `core/evidence/fact_grounder.py` (adapter/migrate)
- `core/tools/gateway.py`
- `core/tools/schemas.py` or `core/api/schemas.py` (new)
- `tests/verification/*` (new)

### Acceptance criteria

- Every outcome contains a four-state status and evidence references.
- A changed subject digest invalidates prior completion evidence.
- Verifier environmental failures never become `PASS` or `FAIL` unless the requirement itself defines them as failure.
- False-pass rate is below 1% on the adversarial verifier suite.
- Core deterministic verifier p95 is below 25 ms excluding spawned commands and network.

---

## WS4 — Trusted memory and persistence decomposition

**Owner profile:** Data/privacy engineer  
**Priority:** P1  
**Starts:** Week 5

### Objectives

Make memory useful, explainable, erasable, and resistant to poisoning while decomposing the 3,000+ line persistence module.

### Memory model additions

Every memory item must include:

- type and normalized content;
- project/user/global scope;
- provenance and producer;
- evidence references;
- trust state;
- sensitivity state;
- created/updated/expiry timestamps;
- contradiction group;
- approval actor and timestamp;
- successful-use and harmful-use counters;
- schema version.

### Trust lifecycle

```text
observed -> quarantined -> approved -> active -> stale -> archived/deleted
                    \-> rejected/deleted
```

Rules:

- Remote, model-generated, contradicted, or low-confidence lessons begin quarantined.
- Sensitive records cannot become active memory.
- Only verified outcomes can automatically propose a lesson.
- Similarity alone never raises trust.
- Contradictory active memories force review or latest-authoritative-source policy.
- “Forget” physically deletes the selected item and dependent searchable representations.

### Persistence refactor tasks

1. Characterize `EliteStore` behavior with tests before extraction.
2. Add explicit database schema version and migration ledger.
3. Extract transaction/connection management.
4. Extract repositories for workflows, memories, telemetry, rules, and sync.
5. Keep `EliteStore` as a compatibility facade until all callers migrate.
6. Add atomic migration backup and restore-on-failure.
7. Test upgrades from every supported minor schema.
8. Add corruption recovery documentation and `doctor --fix` repair actions that never destroy data without confirmation.
9. Add per-project isolation and deletion tests.
10. Measure helpful, harmful, stale, and unused retrieval rates.

### Files affected

- `core/memory/models.py` (new)
- `core/memory/service.py` (new)
- `core/memory/policy.py` (new)
- `core/persistence/database.py` (new)
- `core/persistence/migrations/*` (new)
- `core/persistence/repositories/*` (new)
- `core/memory/persistent_store.py` (compatibility facade)
- `tests/memory/*`, `tests/persistence/*` (new)

### Acceptance criteria

- Upgrade fixtures from each supported schema migrate without data loss.
- Interrupted migrations restore the previous usable state.
- Deletion removes primary, vector, graph, and cached forms.
- Sensitive fixture content never appears in persisted raw form.
- Cross-project memory leakage tests remain zero.

---

## WS5 — Runtime simplification and dependency reduction

**Owner profile:** Staff/core engineer  
**Priority:** P0  
**Starts:** Week 1 discovery; implementation Week 6

### Objectives

Reduce startup surface, maintenance burden, and accidental coupling without a destabilizing rewrite.

### Implementation tasks

1. Generate an import graph rooted at `create_mcp_server(..., tool_profile="core")`.
2. Record baseline:
   - imported module count;
   - startup time and RSS;
   - wheel size;
   - installed dependency count;
   - core-path lines/modules;
   - test duration.
3. Label every module Core, Optional, Experimental, Legacy, or Remove in `docs/module_inventory.yml`.
4. Add a test that default startup does not import forbidden heavy modules.
5. Move Pydantic result models from `core/tools/gateway.py` to `core/api/schemas.py`.
6. Move command execution and verification logic out of the gateway.
7. Reduce `core/integration/mcp_server.py` to composition, transport, and CLI wiring.
8. Choose one supported graph implementation for experimental use; remove versioned graph modules from active package after compatibility review.
9. Exclude experimental modules and their dependencies from the default wheel or place them behind extras.
10. Remove dead placeholders and `NotImplementedError` from production-reachable code.
11. Add module-size and import-boundary checks with an exception manifest.
12. Make `legacy` security-fix-only and document its support deadline.

### Refactor sequence

Never combine behavioral change and module movement in one PR. Use:

1. characterization tests;
2. pure move with compatibility import;
3. caller migration;
4. facade deprecation;
5. dead-path removal.

### Acceptance criteria

- Default startup imports no cognitive graph or provider SDK.
- Core runtime can install without LangChain, LangGraph, SciPy, or NetworkX unless a measured core requirement proves otherwise.
- No production-reachable `NotImplementedError`.
- Default wheel and startup metrics improve against the recorded baseline.
- Core domain modules remain under 500 lines, except documented generated/migration files.

---

## WS6 — Installation, doctor, demo, and release reliability

**Owner profile:** Developer-experience engineer  
**Priority:** P0  
**Starts:** Week 2

### Objectives

Make value visible in five minutes and verify the artifact users actually install.

### CLI additions

```bash
elite-reasoning-mcp init --ide cursor|claude-desktop|continue --dry-run
elite-reasoning-mcp demo --json
elite-reasoning-mcp doctor --json
elite-reasoning-mcp doctor --fix --dry-run
elite-reasoning-mcp export-evidence RUN_ID
```

### Demo specification

The demo is local and deterministic:

1. Compile a constrained coding request.
2. Display source-linked requirements.
3. Verify an intentionally invalid draft/diff and show specific failures.
4. Verify a corrected artifact and show `PASS` results.
5. Show time, data-retention policy, and zero network requests.
6. Exit nonzero if any expected transition fails.

### Release CI matrix

- Python 3.11, 3.12, 3.13.
- Ubuntu, macOS, Windows for clean-wheel smoke.
- Build wheel/sdist once from a tagged source tree.
- Install artifact into a clean environment with no source checkout on `PYTHONPATH`.
- Invoke binary, doctor, demo, and stdio MCP session.
- Discover exactly the five core tools.
- Call every tool through a real `ClientSession`.
- Test database migration from the previous two supported releases.
- Run package metadata and artifact-content checks.
- Generate SBOM and provenance attestation in publish workflow.

### Files affected

- `core/integration/mcp_server.py`
- `core/orchestration/ide_installer.py`
- `scripts/release_check.py`
- `.github/workflows/ci.yml`
- `.github/workflows/publish.yml`
- `tests/test_installed_artifact.py` (new)
- `tests/test_cli_demo.py` (new)

### Acceptance criteria

- The installed wheel, not source imports, passes end-to-end MCP checks.
- `demo` works offline and explains value in under five minutes.
- Installer changes are previewed and require confirmation.
- Upgrade and schema rollback tests pass on all supported platforms.

---

## WS7 — Scientific evaluation platform

**Owner profile:** Evaluation scientist/engineer  
**Priority:** P0 for protocol, P1 for scale  
**Starts:** Week 1

### Objectives

Produce falsifiable, independently reproducible evidence about when Elite helps and when it hurts.

### Experimental design

Use matched tasks and equal budgets across arms:

1. Host model alone.
2. Host model + static checklist containing equivalent guidance.
3. Host model + contract compiler only.
4. Host model + verification only.
5. Full Elite core workflow.

Optional secondary arm: full workflow plus trusted memory.

Evaluate at least:

- three model families;
- small and medium model tiers;
- three seeds for stochastic systems;
- multiple repository types and languages;
- 300+ paired tasks for confirmatory study, after power simulation.

### Primary endpoint

Pre-register one endpoint:

**Paired task success under an equal total-cost budget**, determined by hidden tests or an objective task oracle.

### Secondary endpoints

- explicit constraint satisfaction;
- unsupported completion rate;
- scope violations;
- regression rate;
- citation precision and recall;
- cost and latency per successful task;
- user correction time;
- over-refusal and unnecessary escalation;
- privacy and safety violations.

### Dataset design

- Public development set for iteration.
- Locked hidden confirmatory set.
- Temporal split to reduce contamination.
- Real issue-to-patch tasks and synthetic exact-constraint tasks.
- Adversarial variants and paraphrases.
- Signed manifest with task hashes, environment, seeds, versions, and budgets.
- No hand-written treatment answers.

### Statistical plan

- Exact McNemar test and paired risk difference for paired binary outcomes.
- Bootstrap confidence intervals clustered by task/repository.
- Mixed-effects models for repeated model/seed/task observations.
- Correct secondary endpoints for multiple comparisons.
- Publish exclusions, failures, ties, and missing data.
- Predefine minimum practical effect, non-inferiority safety margins, and stop rules.

### Release decision rule

Do not claim broad benefit unless:

- primary effect exceeds the pre-registered minimum and CI excludes zero;
- no critical safety/privacy endpoint regresses;
- cost per success is within budget;
- no major task family exceeds the allowed regression margin;
- result replicates on a fresh slice;
- scripts and anonymized raw outcomes are published.

### Implementation tasks

1. Replace the current pilot generator with a manifest-driven runner.
2. Separate task generation, candidate execution, anonymization, judging, and analysis roles.
3. Freeze outputs before unmasking treatment labels.
4. Add baseline/checklist/contract/verify/full ablations.
5. Add power simulation based on expected discordant pairs.
6. Produce machine-readable results plus generated Markdown.
7. Add a reproducibility command with environment lock and deterministic fixture mode.
8. Invite an external evaluator after the 300-task internal run.

### Files affected

- `core/eval/*` (refactor)
- `evals/manifests/*` (new)
- `evals/tasks/*` (new or external-data references)
- `scripts/run_evaluation.py` (new)
- `scripts/analyze_evaluation.py` (new)
- `scripts/double_blind_eval.py` (pilot compatibility/deprecate)
- `docs/evaluation_protocol.md` (new)

### Acceptance criteria

- A clean environment reproduces the frozen-fixture analysis exactly.
- Candidate generation uses equal declared budgets.
- Treatment labels remain hidden until scoring is locked.
- Generated report includes negative and null results.
- Independent evaluator can execute the protocol from documentation.

---

## WS8 — Security, privacy, and adversarial reliability

**Owner profile:** Security engineer  
**Priority:** P0  
**Starts:** Week 1

### Threat model

Cover:

- malicious user prompts;
- poisoned local/remote memory;
- prompt injection in retrieved pages;
- hostile MCP payloads;
- command allowlist bypass;
- path traversal and symlinks;
- stale/replayed evidence;
- secret persistence and error leakage;
- partial/corrupted database writes;
- malicious sync endpoints and redirects;
- dependency and release-chain compromise.

### Implementation tasks

1. Publish a data-flow diagram and trust boundaries.
2. Maintain a threat register with mitigation owner and verification test.
3. Fuzz all public structured inputs and parsers.
4. Add property tests for redaction and path/cwd confinement.
5. Treat web content as untrusted data and strip instructions from retrieval context.
6. Bind approvals/evidence to content digest, actor, scope, and expiry.
7. Add replay and TOCTOU tests.
8. Add database interruption and corruption simulations.
9. Add secret canaries across logs, errors, telemetry, memory, exports, and sync.
10. Run dependency review, CodeQL, Bandit, Gitleaks, artifact inspection, and SBOM generation.
11. Commission external security review before enterprise positioning.

### Acceptance criteria

- Zero secret canaries escape expected boundaries.
- No command-prefix or path-confinement bypass in adversarial suite.
- Replayed or stale evidence is rejected.
- Corruption tests either recover safely or provide non-destructive repair guidance.
- Security claims state the tested boundary instead of promising “zero vulnerabilities.”

---

## WS9 — Observability and value reporting

**Owner profile:** Product/data engineer  
**Priority:** P1  
**Starts:** Week 7

### Event model

Record metadata locally by default:

- run and schema version;
- timestamps and durations;
- task family and risk tier;
- selected path;
- verifier names and statuses;
- repair count;
- outcome status;
- error category;
- evidence counts;
- retention mode;
- no raw prompts, drafts, code, or secrets by default.

### User-facing workflow report

```text
Elite verification summary
- 6 requirements: 5 PASS, 1 UNKNOWN
- Prevented completion: tests were not executed
- Scope check: PASS; 2 requested files changed
- Repair attempts: 1
- Local overhead: 47 ms excluding test execution
- Network requests: 0
- Raw prompt retained: no
```

### Implementation tasks

1. Define a versioned local event schema.
2. Add a value report to `elite_verify(check="outcomes")` and CLI export.
3. Distinguish Elite-detected failure from Elite-prevented failure; do not overclaim prevention.
4. Add local aggregate reports for reliability, false positives, repair success, and verifier usage.
5. Add explicit opt-in export with redaction preview.
6. Define design-partner survey hooks for usefulness and false-positive feedback.

### Acceptance criteria

- Users can identify what Elite checked and what remains unknown.
- Telemetry-off mode produces no telemetry records.
- Default events contain no raw prompt/draft/code.
- Product metrics can be computed without conflating detection and prevention.

---

## WS10 — Adoption and ecosystem

**Owner profile:** Founder/product + developer relations  
**Priority:** P1 after reliable demo  
**Starts:** Month 3

### Initial customer profile

Start with one segment:

**Developers or small teams using coding agents for repository changes who suffer from missed explicit requirements and unsupported “done” claims, and who prefer local-first controls.**

### Design-partner program

1. Recruit 10 partners across 2–3 coding-agent hosts.
2. Observe onboarding rather than only sending documentation.
3. Establish baseline workflow and failure data before intervention.
4. Hold weekly review of:
   - setup failures;
   - false positives;
   - missed requirements;
   - skipped tool usage;
   - workflows abandoned due to friction;
   - confirmed prevented/detected failures.
5. Do not build bespoke features unless at least three partners share the problem.

### Funnel metrics

- Install initiated.
- Doctor passed.
- First demo completed.
- First real contract compiled.
- First outcome verified.
- Second-week return.
- Fourth-week retained use.
- User-confirmed useful detection.

### Ecosystem milestone

After verifier API stability, publish an SDK with:

- typed protocol;
- verifier test kit;
- fixture runner;
- security guidance;
- compatibility matrix;
- signed plugin metadata option.

Start with first-party verifiers for Python/pytest and Git diff. Add JavaScript, Rust, and framework-specific plugins based on real usage.

### Acceptance criteria

- >=60% of supported installs complete demo.
- >=35% of activated design partners remain active at Week 4.
- >=70% of sampled verification reports are rated useful.
- <10% disable the product primarily due to friction.
- At least three external verifier prototypes validate SDK ergonomics before declaring API stable.

---

## 5. Delivery roadmap

## Phase 0 — Baseline and credibility reset (Days 1–14)

### Deliverables

- Claims registry validation and corrected README language.
- Current benchmark relabeled as internal pilot.
- Architecture/import/dependency baseline.
- Module inventory with Core/Optional/Experimental/Legacy/Remove status.
- Threat model and data-flow diagram.
- Frozen 250-prompt contract evaluation corpus specification.
- ADRs for product boundary, four-state verification, and package direction.

### Exit gate

No known contradictory claim remains; all future claims are CI-checked. Team agrees not to add reasoning frameworks during the hardening program.

## Phase 1 — Evidence-first core (Days 15–45)

### Deliverables

- Typed requirement and contract models with source spans.
- Four-state verification result and evidence models.
- Verifier registry with constraint, syntax, test-command, and Git-diff verifiers.
- Subject-digest binding and stale-evidence rejection.
- Existing MCP schemas versioned and compatibility-tested.
- Local deterministic demo.

### Exit gate

The full demo compiles constraints, fails bad evidence, accepts corrected evidence, and exposes remaining unknowns through a real MCP client.

## Phase 2 — Runtime and persistence hardening (Days 46–75)

### Deliverables

- Core import boundary enforcement.
- Gateway/server decomposition.
- Minimal default dependency set.
- Persistence migration ledger and repository extraction started.
- Migration backup/restore and corruption tests.
- Installed-wheel cross-platform CI.
- Secret-canary and adversarial test suite.

### Exit gate

Default runtime does not import experimental graph/provider dependencies; clean-wheel tests and upgrade tests pass on all supported platforms.

## Phase 3 — Evaluation and design-partner readiness (Days 76–90)

### Deliverables

- Manifest-driven evaluation harness.
- Five-arm ablation protocol and power analysis.
- 50–100 task internal engineering pilot, clearly non-confirmatory.
- Value report and local operational metrics.
- Onboarding guide, demo video/script, support checklist.
- Design-partner consent/privacy and feedback process.

### Exit gate

The product is ready for 10 external design partners, and the evaluation protocol is frozen before the confirmatory run.

## Phase 4 — External pilot and confirmatory benchmark (Months 4–6)

### Deliverables

- 10 design partners onboarded.
- Weekly reliability and friction review.
- 300+ task confirmatory evaluation with frozen hidden set.
- Published anonymized outcomes, analysis code, and limitations.
- Contract/compiler improvements driven only by development set.
- Memory usefulness metrics and poisoning tests.

### Exit gate

At least one practical benefit is statistically supported without violating safety/cost gates, or claims are narrowed based on null results.

## Phase 5 — Stable core and plugin beta (Months 7–9)

### Deliverables

- Core branch coverage >=90%.
- Legacy support deadline and migration guide.
- Verifier SDK beta and test kit.
- Repository policy file beta.
- Two deep IDE integrations with diagnostics.
- External security review initiated.

### Exit gate

Three external verifier prototypes work without private APIs, and retained user data supports continuing investment.

## Phase 6 — Independent replication and ecosystem (Months 10–12)

### Deliverables

- Independent benchmark reproduction.
- Stable evidence-bundle schema.
- Plugin API v1.
- Enterprise-ready privacy, audit, and policy documentation.
- Public annual reliability/limitations report.

### Exit gate

Broad claims are made only where internal and independent evidence agree. Otherwise, positioning remains scoped to measured task families.

---

## 6. First 20 implementation issues

| # | Issue | Priority | Depends on | Acceptance artifact |
|---:|---|---|---|---|
| 1 | Add claims schema and validator | P0 | — | CI test with deliberate mismatch |
| 2 | Correct README/report claims and statistics | P0 | 1 | Generated claims block |
| 3 | Capture core startup/import/dependency baseline | P0 | — | Versioned baseline JSON |
| 4 | Create module classification inventory | P0 | 3 | `docs/module_inventory.yml` |
| 5 | Add architecture decision records | P0 | — | Three accepted ADRs |
| 6 | Define typed requirement/contract schemas | P0 | 5 | Schema snapshots |
| 7 | Add source-span requirement extraction | P0 | 6 | Golden corpus tests |
| 8 | Define evidence and four-state result schemas | P0 | 5 | Schema snapshots |
| 9 | Build verifier protocol and registry | P0 | 8 | Registry unit tests |
| 10 | Migrate constraint and syntax checks | P0 | 9 | Compatibility tests |
| 11 | Harden test-command verifier | P0 | 9 | Bypass/adversarial tests |
| 12 | Add Git-diff scope verifier | P0 | 9 | Scope fixture suite |
| 13 | Bind evidence to subject digest | P0 | 8–12 | Stale evidence rejection test |
| 14 | Version MCP response contracts | P0 | 6, 8 | Protocol snapshot tests |
| 15 | Implement deterministic CLI demo | P0 | 7–14 | Installed-wheel demo CI |
| 16 | Add core forbidden-import test | P0 | 3–4 | Test fails on LangGraph import |
| 17 | Split default dependency extras | P0 | 16 | Minimal clean install |
| 18 | Add installed-wheel OS matrix | P0 | 15, 17 | Linux/macOS/Windows CI |
| 19 | Add DB migration ledger/backup | P1 | characterization tests | Upgrade/rollback fixtures |
| 20 | Build manifest-driven evaluation runner | P1 | schemas stable | Reproducible fixture report |

Each issue must include tests, documentation impact, migration impact, security impact, and metric impact. Avoid issues larger than five engineering days; split them by vertical behavior rather than file layer when possible.

---

## 7. Engineering process and quality gates

### Pull-request template additions

Every PR must answer:

- Which user-visible outcome changes?
- Which product metric should move?
- Is this Core, Optional, Experimental, Legacy, or Removal?
- Does it change a public schema or persisted schema?
- What evidence demonstrates correctness?
- What failure/unknown behavior was tested?
- Does default startup import or dependency count change?
- Does the PR add or alter a public claim?

### Required CI lanes

1. Fast unit tests and Ruff.
2. Strict typing for the complete core path.
3. Architecture/import-boundary tests.
4. Core branch coverage.
5. Property/adversarial verifier tests.
6. Privacy secret-canary tests.
7. Database upgrade/rollback tests.
8. Installed-wheel MCP integration tests.
9. Claim validation.
10. Nightly mutation, fuzz, and extended benchmark lanes.

### Definition of done

A feature is done only when:

- typed public/domain models exist;
- deterministic and failure-path tests pass;
- `UNKNOWN` behavior is explicit;
- telemetry/value-report behavior is defined;
- privacy and migration implications are handled;
- user documentation is updated;
- no unsupported claim is introduced;
- installed-artifact integration passes.

---

## 8. Staffing model

### Minimum sustainable team

- 1 product/technical lead.
- 2 core Python engineers.
- 1 evaluation/data engineer.
- 0.5 security/privacy engineer.
- 0.5 developer experience/community owner.

If only one maintainer is available, execute sequentially:

1. claims and product boundary;
2. schemas and verifier core;
3. installed-artifact reliability;
4. architecture reduction;
5. 50-task pilot;
6. design partners;
7. only then scale evaluation and plugins.

Do not attempt the 12-month plan concurrently as a solo maintainer.

---

## 9. Key risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Refactor breaks existing MCP clients | Medium | High | Compatibility facades, schema snapshots, installed-client tests |
| Contract compiler invents requirements | Medium | High | Source spans, confidence, proposed state, frozen labeled corpus |
| Verifier creates false confidence | Medium | Critical | Four-state results, evidence binding, adversarial and mutation tests |
| Forced workflow adds more friction than value | High | High | Risk router, skip path, report overhead, user opt-out metrics |
| Evaluation overfits development tasks | High | High | Locked temporal test set, preregistration, external replication |
| Large dependency reduction removes valued features | Medium | Medium | Extras, usage evidence, compatibility period |
| Memory poisoning causes repeated bad guidance | Medium | High | Quarantine, provenance, verified-outcome promotion only |
| Solo-maintainer scope overwhelms delivery | High | High | 90-day sequence, WIP limit, no new frameworks, vertical issues |
| Public correction of claims appears negative | Medium | Medium | Explain maturity and reproducibility; trust gain outweighs short-term optics |
| Adoption remains weak despite engineering quality | Medium | High | Design partners by Month 3; stop/go criteria at Month 6 |

---

## 10. Stop/go decisions

### Day 45

**Continue architecture investment if:** the evidence-first demo works and verifier false-pass rate is below 1% on current adversarial fixtures.  
**Otherwise:** stop refactoring and fix verifier semantics.

### Day 90

**Begin external pilot if:** clean install succeeds, core tool reliability meets 99.5% automated gate, privacy tests pass, and onboarding takes under five minutes.  
**Otherwise:** do not recruit broadly; fix reliability.

### Month 6

**Expand product/ecosystem if:** design partners show >=35% Week-4 retention and a measurable reduction in unsupported completion or requirement misses.  
**Narrow or pivot if:** users do not retain, false positives cause disabling, or full workflow does not beat an equivalent static checklist.

### Month 12

**Use broad market claims only if:** confirmatory and independent results agree.  
**Otherwise:** market only the specific verified capabilities—local contracts, evidence bundles, policy checks, and trusted memory.

---

## 11. Score targets and proof required

| Dimension | Current assessment | Path to 10/10 | Proof required |
|---|---:|---|---|
| Real implementation | 8 | Reliable artifact, migrations, recovery, cross-platform E2E | Clean-wheel and observed reliability data |
| Core product idea | 8 | Source-linked contracts + evidence gate + trusted memory | User preference over equivalent checklist |
| Engineering ambition | 9 | Verifier ecosystem and portable evidence protocol | External plugins and cross-agent bundles |
| Focus/maintainability | 5 | Small dependency-light core, experimental isolation | Import graph, complexity, coverage, contributor lead time |
| Scientific evidence | 3 | Pre-registered 300+ task study and replication | Raw results, analysis, independent reproduction |
| Market validation | 1 | Activated and retained external users | Cohort retention and confirmed useful detections |
| Long-term potential | 7 | Repository policies and agent-independent evidence standard | Multi-host adoption and ecosystem usage |

A “10/10” is not a release label. It is an evidence threshold. Scores must not be raised because planned work exists; they move only when the corresponding proof is available.

---

## 12. Immediate next action

Create a 90-day milestone and open Issues 1–5 first. The first implementation PR should add the claims validator and correct public claims. The second should establish architecture and runtime baselines. Only after those merge should schema and verifier refactoring begin.

The operating rule for the entire program is:

> **No new reasoning feature until the core is smaller, its claims are consistent, its verifier results are evidence-bound, and external users demonstrate retained value.**
