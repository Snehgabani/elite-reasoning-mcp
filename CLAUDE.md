# Elite Reasoning MCP — Continuous Checkpoint Protocol

For every non-trivial coding task:

1. Call `elite_prepare(user_prompt=<exact request>, persist=true)` before editing and retain its `run_id`.
2. Read the `continuation` object returned by every Elite tool call.
3. When `continuation.stop_final_response=true`, do not answer the user. Invoke `continuation.required_tool` using `continuation.required_args` with current code, repository root, tests, or draft substituted for placeholders.
4. The normal lifecycle is `prepare → syntax after edit → Git scope → executed tests → outcomes`.
5. A `FAIL`, `UNKNOWN`, `NOT_CHECKED`, `REPEAT`, or stale-evidence response means repair and follow the newly returned continuation directive.
6. Respond to the user only when `continuation.checkpoint="done"` and `stop_final_response=false`.

This rule addresses model tool amnesia through repeated host-visible directives. MCP alone cannot force a host model to make another call, so never describe this as absolute enforcement unless an active external hook blocks the action.
