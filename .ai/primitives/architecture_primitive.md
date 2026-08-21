# Primitive: Architecture Design
## Trigger: System design, component structure, API design, data models
## Reasoning Graph Template:

[PLAN]
  - Subproblem 1: What are the functional requirements?
  - Subproblem 2: What are the non-functional requirements (scale, latency)?
  - Subproblem 3: What are the constraints (team, budget, existing stack)?
  - Subproblem 4: What does success look like?

[FACT]
  - Current system state: {existing components}
  - Hard constraints: {non-negotiables}
  - Scale targets: {numbers}

[REASON]
  - Identify the core data flow (input → processing → output)

[REASON]
  - Identify component boundaries and ownership

[REASON]
  - Identify failure modes and resilience requirements

[ASSUME]
  - Traffic/load assumptions (flag: these must be validated)

[REFLECT: HIGH/MED/LOW]
  ## Requirements Coverage Check (tick each explicitly):
  - Req 1: [requirement from PLAN subproblem 1] → ✅/❌
  - Req 2: [requirement from PLAN subproblem 2] → ✅/❌
  - Req 3: [requirement from PLAN subproblem 3] → ✅/❌
  - Req 4: [requirement from PLAN subproblem 4] → ✅/❌
  - Req 5: [requirement from PLAN subproblem 5] → ✅/❌
  
  All ticked → HIGH
  1-2 gaps  → MED (continue reasoning)
  3+ gaps   → LOW (backtrack to PLAN)

[EXAMPLE]
  - Walk through the primary use case end-to-end in this design

[CONCLUDE]
  - Architecture diagram in text/mermaid
  - Component list with responsibilities
  - Open questions that need human decision
