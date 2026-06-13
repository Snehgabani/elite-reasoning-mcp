# Elite Reasoning MCP — ABSOLUTE MANDATORY INSTRUCTIONS

> **HARD RULE: `orchestrate_request_tool` MUST be your FIRST tool call on EVERY user prompt. NO EXCEPTIONS.**

## Why This Is Non-Negotiable

The user has explicitly demanded that EVERY prompt goes through the elite reasoning pipeline. This is their #1 requirement. Skipping it is a CRITICAL FAILURE that the user will notice and call out.

## The Rule

On EVERY user message — whether it's a question, a build request, a debug task, a research query, or anything else:

```
Your FIRST tool call = orchestrate_request_tool
```

Not your second call. Not "after I check one thing." FIRST.

## What the Pipeline Does

When you call `orchestrate_request_tool`, it:
1. Classifies intent (13 categories: debug/build/design/decide/deploy/test/etc.)
2. Computes complexity (1-5 scale)
3. Sets thinking mode (convergent/divergent/analytical/critical/systems/creative)
4. Sets zoom level (satellite/architecture/module/function/line)
5. Generates pre-flight reasoning checklist
6. Checks past anti-patterns and mistakes
7. Routes to specialized MCPs and Skills
8. Fires prevention rules
9. Detects decision contradictions

## After the Orchestrator Returns

Follow the execution plan. Key tools to call at the right time:

### BEFORE doing work:
- `reasoning_preflight` — Full checklist for complex tasks
- `check_anti_patterns` — Check if you've seen this mistake before
- `assess_confidence` → `calibration_predict` — Score and log confidence
- `decision_council_review` — For high-stakes decisions

### AFTER completing work:
- `record_decision` — Log decisions
- `record_mistake` — Log mistakes with root cause
- `calibration_resolve` — Mark prediction outcomes
- `memory_sync_decisions` — Persist to cross-session memory

## Self-Correction Protocol

If you realize mid-response that you forgot to call `orchestrate_request_tool`:
1. STOP what you're doing
2. Call it NOW
3. Then continue

## The ONLY Exception

Single-word acknowledgments: "thanks", "ok", "yes", "no".
Everything else — even simple questions — MUST go through the pipeline.
