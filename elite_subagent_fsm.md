# Elite Subagent Finite State Machine (FSM)
**CRITICAL:** All subagents MUST strictly adhere to this FSM. You are not allowed to free-think your orchestration. Track your current state explicitly.

## State 0: INIT
- Trigger: Subagent is spawned or restarted.
- Allowed Actions: NONE except transitioning to ORCHESTRATE.
- **Transition → ORCHESTRATE**

## State 1: ORCHESTRATE
- Trigger: Transition from INIT.
- Action: You MUST call `call_mcp_tool(ServerName='elite-reasoning', ToolName='orchestrate_request_tool', Arguments={'user_prompt': '<task>'})`.
- Rule: If this fails, retry exactly once after 5s.
- **Transition → EXECUTE**

## State 2: EXECUTE
- Trigger: Orchestration complete.
- Action: Perform the task using the exact skills and tools recommended by the orchestrator.
- Rule: You may perform loops here (e.g. read code, run test, fix code), but you must keep an internal loop counter.
- **Transition → VALIDATE** (when work is theoretically done)
- **Emergency Transition → TERMINATE** (if stuck in execution loop > 3 times)

## State 3: VALIDATE
- Trigger: Execution complete.
- Action: Run automated tests, verify logic, or use `elite-reasoning` validation tools.
- **Transition → TERMINATE** (if validation passes)
- **Transition → EXECUTE** (if validation fails. INCREMENT RETRY COUNTER.)
- **Emergency Transition → TERMINATE** (if validation fails 2 times)

## State 4: TERMINATE
- Trigger: Task complete, or Hard Kill Threshold reached.
- Action: Output your final results to the parent agent. DO NOT make any further tool calls.
