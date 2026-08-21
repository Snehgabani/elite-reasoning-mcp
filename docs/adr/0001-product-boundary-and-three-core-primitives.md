# ADR 0001: Product Boundary & Three Core Production Primitives

## Status
Accepted

## Context
The early prototype explored over 50+ experimental prompt reasoning heuristics (e.g. Tree of Thoughts, Storm Research, Epistemic Divergence). While educational, this bloated the dependency graph, introduced cognitive complexity, and created uncalibrated quality claims.

## Decision
We freeze expansion of reasoning methods and concentrate 100% of engineering bandwidth on three core primitives:
1. **Contract Compiler**: Convert user requests into source-linked, machine-checkable requirement constraints.
2. **Evidence-Backed Completion Gate**: Classify every expected outcome as `PASS`, `FAIL`, `UNKNOWN`, or `NOT_CHECKED` using cryptographically bound evidence.
3. **Trusted Local Memory**: Retain compact, scoped, provenance-rich lessons with quarantine protection against memory poisoning.

## Consequences
- The public MCP surface is restricted to the minimalist 5-tool interface (`elite_prepare`, `elite_progress`, `elite_verify`, `elite_memory`, `elite_admin`).
- Non-core reasoning graphs are placed behind experimental extras or scheduled for deprecation.
