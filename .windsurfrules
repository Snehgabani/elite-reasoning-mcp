# Elite Reasoning MCP — Continuous Checkpoint Protocol & Native Tool Interlock

For every non-trivial coding task:
1. Checkpoint 1 (Pre-Edit): Call `elite_prepare(user_prompt=<exact request>, persist=true)` and retain `run_id`.
2. Checkpoint 2 (During-Edit): You are strictly prohibited from calling native edit tools (`replace_file_content`, `write_to_file`) without immediately executing their coupled MCP verifier:
   - Call `elite_verify(check="syntax", code="...")` and `elite_verify(check="cegis", code="...")`.
   - If an error occurs, call `elite_verify(check="diagnostics", query="<traceback>")`.
3. Checkpoint 3 (Post-Edit): Run executed test and Git diff evidence via `elite_verify(check="tests")` and `elite_verify(check="git_diff")`.
4. Read `continuation` after every Elite response. If `stop_final_response=true`, call `required_tool` with `required_args`; do not answer yet.
5. Answer only when checkpoint is `done` and `stop_final_response=false`.

MCP cannot force another host call. IDE rules, durable state, evidence gates, and optional Git hooks are layered mitigation—not absolute enforcement.
