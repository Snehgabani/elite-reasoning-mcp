from core.eval.open_source_integrations import (
    INTEGRATIONS,
    integrations_markdown,
    recommend_open_source_integrations,
)


def test_manifest_includes_core_optional_frameworks_and_local_providers():
    names = {integration.name for integration in INTEGRATIONS}

    assert "GEPA / DSPy" in names
    assert "Promptfoo" in names
    assert "DeepEval" in names
    assert "Inspect AI" in names
    assert "Ollama" in names
    assert "llama.cpp" in names
    assert "vLLM" in names


def test_recommend_integrations_filters_by_red_team_ci_use_case():
    data = recommend_open_source_integrations("red team prompt injection ci")
    names = {recommendation["name"] for recommendation in data["recommendations"]}

    assert "Promptfoo" in names
    assert data["dependency_policy"].startswith("Core MCP remains dependency-light")


def test_recommend_integrations_for_local_model_mentions_providers():
    data = recommend_open_source_integrations("local open-source model provider")
    names = {recommendation["name"] for recommendation in data["recommendations"]}

    assert {"Ollama", "llama.cpp", "vLLM"} & names
    assert all(recommendation["install_commands"] for recommendation in data["recommendations"])


def test_integrations_markdown_contains_install_commands_and_json():
    rendered = integrations_markdown("prompt optimization")

    assert "# Optional Open-Source Integration Recommendations" in rendered
    assert "GEPA / DSPy" in rendered
    assert "Install commands" in rendered
    assert "## JSON" in rendered
