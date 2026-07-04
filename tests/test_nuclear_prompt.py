from core.reasoning.nuclear_prompt import (
    break_down_prompt,
    nuclear_prompt_breakdown,
    nuclear_prompt_markdown,
    protocol_recommendation,
    select_reasoning_protocol,
)


def test_nuclear_prompt_breakdown_extracts_core_sections():
    prompt = (
        "Upgrade the MCP with research-backed benchmarks, add tests, keep GEPA and Promptfoo optional, "
        "and validate the installed tool after restart."
    )

    breakdown = break_down_prompt(prompt)
    data = breakdown.to_dict()

    assert breakdown.user_goal.startswith("Upgrade the MCP")
    assert "explicit_requirements" in data
    assert any("Upgrade the MCP" in requirement for requirement in breakdown.explicit_requirements)
    assert any("optional" in constraint.lower() for constraint in breakdown.constraints)
    assert any("benchmark" in evidence.lower() for evidence in breakdown.needed_evidence)
    assert any("validation" in item.lower() or "tests" in item.lower() for item in breakdown.success_criteria)
    assert "capability_verification" in breakdown.allowed_tools


def test_nuclear_prompt_markdown_includes_json_payload():
    rendered = nuclear_prompt_markdown("Fix a failing test and explain the root cause.")

    assert "# Nuclear Prompt Breakdown" in rendered
    assert "## JSON" in rendered
    assert '"validation_plan"' in rendered
    assert "Self" not in rendered  # protocol selection is intentionally separate


def test_protocol_selection_prefers_research_for_benchmark_prompts():
    recommendation = select_reasoning_protocol(
        "Research benchmark evidence and compare model quality for open-source LLMs.",
        complexity=5,
    )

    assert recommendation.selected_protocol == "Evidence-Grounded Research"
    assert "Self-Consistency" in recommendation.supporting_protocols
    assert any("evidence" in step.lower() for step in recommendation.execution_steps)


def test_protocol_selection_prefers_self_debugging_for_failures():
    recommendation = protocol_recommendation("Fix this crashing MCP test failure and rerun pytest", complexity=3)

    assert recommendation["selected_protocol"] == "Self-Debugging"
    assert "ReAct" in recommendation["supporting_protocols"]


def test_protocol_selection_stays_direct_for_low_risk_prompt():
    recommendation = select_reasoning_protocol("Say hi", complexity=1)

    assert recommendation.selected_protocol == "direct"


def test_json_breakdown_api_is_model_agnostic_dict():
    data = nuclear_prompt_breakdown("Configure an MCP server safely without hard dependencies")

    assert isinstance(data, dict)
    assert set(data) >= {
        "user_goal",
        "explicit_requirements",
        "implicit_requirements",
        "constraints",
        "risk_areas",
        "needed_evidence",
        "success_criteria",
        "allowed_tools",
        "validation_plan",
        "stop_conditions",
    }
