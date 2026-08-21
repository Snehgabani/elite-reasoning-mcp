# Primitive: Debug
## Trigger: Any bug, error, exception, unexpected behavior
## Reasoning Graph Template:

[PLAN]
  - Subproblem 1: What is the exact error message?
  - Subproblem 2: What is the call stack?
  - Subproblem 3: What is the last working state?
  - Subproblem 4: What changed between working and broken?

[FACT]
  - Exact error text: {paste error}
  - File and line number: {file:line}
  - Language/runtime version: {version}

[REASON]
  - Trace execution path from entry point to failure line

[REASON]
  - Identify which variable/state is wrong at failure point

[ASSUME]
  - Hypothesis about root cause (may be wrong — label it)

[REFLECT: HIGH/MED/LOW]
  - Does hypothesis explain ALL symptoms? If NO → confidence LOW
  - If LOW: backtrack to [PLAN], open new branch with different hypothesis

[EXAMPLE]
  - Minimal reproducible case that isolates the bug

[CONCLUDE]
  - Root cause: {cause}
  - Fix: {exact code change}
  - Prevention: {what to do to avoid recurrence}
