from core.reasoning.constraint_check import check_draft
from core.reasoning.task_contract import compile_task_contract, contract_markdown


def test_contract_extracts_checkable_constraints_for_cheap_models():
    contract = compile_task_contract(
        "Reply in JSON with keys ok and reason. At most 40 words. Do not mention tools. Must include pytest."
    )

    kinds = {item.kind for item in contract.constraints}
    assert "max_words" in kinds
    assert "format" in kinds
    assert "must_not" in kinds
    assert contract.next_action in {"none", "evidence", "verify_constraints", "verify_tests"}
    assert "Task Contract" in contract_markdown(contract)
    assert contract.max_tool_calls <= 4


def test_research_prompt_routes_to_evidence_and_cite_quotes():
    contract = compile_task_contract("Research MCP tool overhead and cite sources with URLs.")

    assert contract.next_action == "evidence"
    assert any(item.kind == "cite_quotes" for item in contract.constraints)


def test_constraint_checker_is_binary_and_rejects_fake_success_json():
    prompt = "Fix the bug. Must run pytest. Do not claim SUCCESS without a log."
    contract = compile_task_contract(prompt)
    good = check_draft("Root cause was a None check. pytest passed in 0.12s.", contract)
    bad = check_draft("SUCCESS. quality_score=0.95 proof_of_work=abc. Fixed.", contract)

    assert good.pass_rate > bad.pass_rate
    assert bad.passed is False


def test_playbook_names_only_core_tools_and_verify_can_repeat():
    from core.reasoning.playbook import allowed_tools_for, compile_playbook, verify_outcomes

    contract = compile_task_contract("Research MCP tool overhead and cite sources with URLs.")
    tools = allowed_tools_for(contract)
    assert set(tools) <= {"elite_prepare", "elite_progress", "elite_verify", "elite_memory", "elite_admin"}
    assert "execute_mix" not in tools
    assert "god_tier_reasoning" not in tools
    steps = compile_playbook(contract)
    assert steps[-1].tool == "elite_verify"
    assert steps[-1].args.get("check") == "outcomes"

    failed = verify_outcomes("I just know this is true.", contract)
    assert failed["action"] == "REPEAT"
    assert failed["passed"] is False

    passed = verify_outcomes(
        'MCP schemas add tokens. "tool definitions sitting in context permanently" https://example.com/mcp-tax',
        contract,
    )
    assert passed["action"] in {"DONE", "REPEAT"}
    assert passed["pass_rate"] >= failed["pass_rate"]
