# Primitive: Code Review
## Trigger: PR review, code quality check, security audit
## Reasoning Graph Template:

[PLAN]
  - Subproblem 1: What does this code claim to do?
  - Subproblem 2: Does it actually do that?
  - Subproblem 3: Security surface (inputs, auth, data exposure)?
  - Subproblem 4: Performance implications?

[FACT]
  - Language/framework version: {version}
  - Code size (lines): {n}
  - Context: {what system this belongs to}

[REASON]
  - Read the code's actual control flow (not what comments say)

[REASON]
  - Identify all external inputs and whether they are validated

[REASON]
  - Check error handling completeness

[ASSUME]
  - Assumed deployment context (flag: confirm with team)

[REFLECT: HIGH/MED/LOW]
  - Would I trust this code in production today?
  - Are there any MUST-FIX issues (security/correctness)?

[CONCLUDE]
  - CRITICAL (block PR): {list}
  - IMPORTANT (fix before merge): {list}
  - SUGGESTED (nice to have): {list}
  - APPROVED: YES/NO
