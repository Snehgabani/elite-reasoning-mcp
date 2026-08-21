"""Tests for SmallModelAdapter cognitive scaffolding."""

from core.cognitive.leverage.small_model_adapter import SmallModelAdapter


def test_small_model_prompt_adaptation():
    adapter = SmallModelAdapter()
    adapted = adapter.adapt_task(
        task="Implement a distributed concurrent LRU cache with TTL eviction in Go",
        current_step=1,
        total_steps=4,
        step_goal="Design data structures and mutex locking strategy",
        context_hints=["Use sync.RWMutex for concurrent safety", "Use container/list for O(1) eviction"],
    )

    assert "[STEP 1/4 COGNITIVE HARNESS]" in adapted.condensed_prompt
    assert "sync.RWMutex" in adapted.condensed_prompt
    assert adapted.expected_output_schema["type"] == "object"
    assert len(adapted.injected_invariants) >= 3


def test_small_model_output_repair_markdown_fences():
    adapter = SmallModelAdapter()
    messy_output = """```json
    {
      "step_index": 1,
      "action_type": "diff",
      "payload": "type Cache struct { mu sync.RWMutex }",
      "verification_rationale": "Valid Go struct",
    }
    ```"""

    repaired = adapter.validate_and_repair_slm_output(messy_output)
    assert repaired["step_index"] == 1
    assert repaired["action_type"] == "diff"
    assert "type Cache struct" in repaired["payload"]


def test_small_model_output_repair_raw_fallback():
    adapter = SmallModelAdapter()
    unparseable_output = "I recommend using a doubly linked list with a hash map."

    repaired = adapter.validate_and_repair_slm_output(unparseable_output)
    assert repaired["step_index"] == 1
    assert repaired["action_type"] == "reasoning"
    assert "doubly linked list" in repaired["payload"]
    assert repaired.get("repaired") is True
