import json
import pytest
from core.cognitive.leverage.param_coercion import ParameterCoercionEngine
from core.cognitive.leverage.small_model_adapter import SmallModelAdapter
from core.cognitive.leverage.micro_scaffold import MicroStepScaffolder


def test_param_coercion_fences_and_noise():
    raw = """Here is the result you asked for:
```json
{
  "count": "42",
  "enabled": "true",
  "tags": ["a", "b", "c"],
  "score": "98.5",
}
```
Hope this helps!"""
    engine = ParameterCoercionEngine()
    repaired_json = engine.repair_json_string(raw)
    parsed = json.loads(repaired_json)
    assert parsed["count"] == "42"

    schema = {
        "properties": {
            "count": {"type": "integer"},
            "enabled": {"type": "boolean"},
            "score": {"type": "number"},
            "tags": {"type": "array"},
        }
    }
    coerced = engine.coerce_parameters(parsed, schema)
    assert coerced["count"] == 42
    assert coerced["enabled"] is True
    assert coerced["score"] == 98.5
    assert coerced["tags"] == ["a", "b", "c"]


def test_param_coercion_unquoted_keys_and_single_quotes():
    raw = "{ step: 1, action: 'query', done: True, }"
    engine = ParameterCoercionEngine()
    parsed = engine.parse_and_repair(raw)
    assert parsed.get("step") == 1
    assert parsed.get("action") == "query"
    assert parsed.get("done") is True


def test_schema_compaction():
    adapter = SmallModelAdapter()
    full_schema = {
        "type": "object",
        "description": "Very long essay explaining how the tool works in multiple paragraphs...",
        "properties": {
            "task": {
                "type": "string",
                "description": "The exact user task described in complete detail with multiple examples.",
            },
            "enable_prm": {
                "type": "boolean",
                "description": "Whether or not to enable Process Reward Models for fine-grained verification.",
                "default": True,
            },
            "task_type": {
                "type": "string",
                "enum": ["fast_path", "hard_problem"],
                "description": "Execution route mode.",
            },
        },
        "required": ["task"],
    }
    compact = adapter.compact_tool_schema(full_schema)
    assert compact["required"] == ["task"]
    assert "description" not in compact["properties"]["task"]
    assert compact["properties"]["enable_prm"]["default"] is True
    assert compact["properties"]["task_type"]["enum"] == ["fast_path", "hard_problem"]


def test_micro_scaffolder_workflow():
    scaffolder = MicroStepScaffolder()

    def mock_generator(prompt: str) -> str:
        return """```json
{
  "step_index": 1,
  "action_type": "reasoning",
  "payload": "Analyzed invariants successfully",
  "verification_rationale": "All rules verified",
}
```"""

    execution = scaffolder.run_scaffolded_workflow(
        task="Refactor database connection pool and verify thread safety",
        generator_fn=mock_generator,
        max_steps=3,
    )
    assert execution.is_success is True
    assert len(execution.completed_steps) == 3
    assert execution.final_payload == "Analyzed invariants successfully"
    assert execution.total_duration_ms > 0
