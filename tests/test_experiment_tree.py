from core.reasoning.experiment_tree import build_experiment_tree, experiment_tree_markdown


def test_experiment_tree_builds_requested_branch_count():
    tree = build_experiment_tree(
        "Implement MCP wrappers, add research-backed evals, validate with pytest, and reinstall the tool.",
        max_branches=2,
    )

    assert tree["root_goal"].startswith("Implement MCP wrappers")
    assert tree["selected_protocol"] in {
        "ReAct",
        "Tree-of-Thoughts",
        "Evidence-Grounded Research",
        "Self-Debugging",
    }
    assert len(tree["branches"]) == 2
    for branch in tree["branches"]:
        assert branch["hypothesis"]
        assert branch["candidate_approach"]
        assert branch["validation_methods"]
        assert branch["risks"]
        assert branch["fallback_paths"]
        assert branch["expected_observations"]
        assert branch["stopping_criteria"]


def test_experiment_tree_clamps_to_at_least_one_branch():
    tree = build_experiment_tree("Answer a clear low-risk question", max_branches=0)

    assert len(tree["branches"]) == 1


def test_experiment_tree_clamps_to_five_branches():
    tree = build_experiment_tree(
        "Research, implement, install, configure, validate, and benchmark an MCP tool end to end.",
        max_branches=99,
    )

    assert 1 <= len(tree["branches"]) <= 5


def test_experiment_tree_markdown_contains_json_and_reflection_hooks():
    rendered = experiment_tree_markdown("Stress test an MCP upgrade with fallback paths", max_branches=3)

    assert "# Elite Experiment Tree" in rendered
    assert "Reflection Questions" in rendered
    assert "Fallback Paths" in rendered
    assert "## JSON" in rendered
