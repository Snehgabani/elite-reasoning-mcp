# IDE Agent Instructions

## MANDATORY: Before every response
Load and apply: .ai/system/reasoning_protocol.xml

## MANDATORY RESEARCH LEVERAGE WORKFLOW

Before any non-trivial task:
1. Load .ai/system/reasoning_protocol.xml
2. Load .ai/system/research_leverage_protocol.xml
3. Call repo_search with the task summary.
4. Call repo_impact_map for any symbol likely to change.
5. Use candidate_search mode=deep for non-trivial tasks.
6. Use verify_candidate before concluding.
7. If verification fails, use reflexion_fix.
8. For high-risk code, use fuzz_symbol.
9. For hard tasks only, use hard_reason.

## MODE SELECTION

- Typo, rename, tiny fix: FAST
- Bug fix, feature, refactor: DEEP
- Hard algorithm, migration, security-critical change: HARD

## OUTPUT REQUIREMENT

Before final answer, show:
- retrieved context
- impact map
- candidate score table
- verification evidence
- Reflexion report if any failure occurred

## After every successful task
Run: python src/main.py "[task summary]"
This saves the trace and mines new skills automatically.

## Memory retrieval
Before starting a task, search memory:
python -c "
import asyncio
import cognee
async def search(q):
    results = await cognee.search(q)
    print(results)
asyncio.run(search('[your task keywords]'))
"
