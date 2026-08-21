# ADR 0002: Four-State Verification & Subject Digest Binding

## Status
Accepted

## Context
Binary pass/fail or uncalibrated float scores (e.g., `0.98`) create false confidence. When an external tool or test fails due to environmental conditions (e.g. network timeout, missing compiler), mapping it to `PASS` or `FAIL` is scientifically invalid.

## Decision
We enforce a strict 4-state verification model:
- `PASS`: Objective verification succeeded against valid evidence.
- `FAIL`: Constraint or test demonstrably failed.
- `UNKNOWN`: Environmental, network, or tool failure prevented conclusive verification.
- `NOT_CHECKED`: Requirement was skipped or not authorized.

All verification evidence must be bound to a SHA-256 digest of the evaluated subject (draft code, diff, or query) to prevent stale evidence reuse.

## Consequences
- Never map "did not crash" to `PASS`.
- Unresolved critical `UNKNOWN` states block certification.
