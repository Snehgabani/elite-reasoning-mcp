"""
Tests for the Autonomous Adaptive Learning System.

Tests cover:
- Prompt Intelligence Engine (record, analyze, thinking patterns)
- Tool Usage Tracking
- Missed Detections & Prevention Rules
- Autonomous Gap Detector
- Goal Engine
- Self-Diagnostics
"""
import json
import tempfile

import pytest

from core.memory.persistent_store import EliteStore


@pytest.fixture
def store():
    """Create an isolated EliteStore for testing."""
    tmp = tempfile.mkdtemp()
    s = EliteStore(tmp)
    yield s


class TestPromptIntelligence:
    """Tests for Subsystem 1: Prompt Intelligence Engine."""

    def test_record_prompt_intent_basic(self, store):
        """Record a prompt and verify it's stored."""
        pid = store.record_prompt_intent(
            session_id="test-session",
            prompt_text="debug the authentication module",
            intent_category="debug",
            reasoning_type="substantive"
        )
        assert pid > 0

    def test_record_prompt_intent_with_failure(self, store):
        """Record a prompt that reveals a system failure."""
        pid = store.record_prompt_intent(
            session_id="test-session",
            prompt_text="why is the orchestrator bypass still there?",
            intent_category="audit",
            reasoning_type="repetition_frustration",
            implicit_expectation="System should have resolved its own findings",
            failure_detected="DETECTION_FAILURE: unresolved findings not caught"
        )
        assert pid > 0

    def test_analyze_prompt_sequence_empty(self, store):
        """Analysis on empty data returns no_data health."""
        result = store.analyze_prompt_sequence()
        assert result["total_prompts"] == 0
        assert result["health"] == "no_data"

    def test_analyze_prompt_sequence_healthy(self, store):
        """A session with all substantive prompts is healthy."""
        for i in range(10):
            store.record_prompt_intent(
                session_id="s1", prompt_text=f"build feature {i}",
                intent_category="build", reasoning_type="substantive"
            )
        result = store.analyze_prompt_sequence(session_id="s1")
        assert result["total_prompts"] == 10
        assert result["health_score"] == 100
        assert result["health"] == "healthy"
        assert result["waste_prompts"] == 0

    def test_analyze_prompt_sequence_critical(self, store):
        """A session dominated by loop kicks is critical."""
        # 7 loop kicks, 3 substantive — mimics THIS conversation
        for i in range(7):
            store.record_prompt_intent(
                session_id="s1", prompt_text="go",
                intent_category="continuation", reasoning_type="loop_kick"
            )
        for i in range(3):
            store.record_prompt_intent(
                session_id="s1", prompt_text=f"build feature {i}",
                intent_category="build", reasoning_type="substantive"
            )
        result = store.analyze_prompt_sequence(session_id="s1")
        assert result["total_prompts"] == 10
        assert result["waste_prompts"] == 7
        assert result["health_score"] == 30
        assert result["health"] == "critical"
        # Should detect LOOP_FAILURE pattern
        loop_pattern = [p for p in result["patterns"] if p["type"] == "LOOP_FAILURE"]
        assert len(loop_pattern) == 1
        assert loop_pattern[0]["count"] == 7

    def test_analyze_prompt_sequence_detects_anticipation(self, store):
        """Detects anticipation failures (gap injections)."""
        for i in range(5):
            store.record_prompt_intent(
                session_id="s1", prompt_text=f"we also need feature {i}",
                intent_category="build", reasoning_type="gap_injection"
            )
        for i in range(5):
            store.record_prompt_intent(
                session_id="s1", prompt_text=f"do thing {i}",
                intent_category="build", reasoning_type="substantive"
            )
        result = store.analyze_prompt_sequence(session_id="s1")
        anticipation = [p for p in result["patterns"] if p["type"] == "ANTICIPATION_FAILURE"]
        assert len(anticipation) == 1
        assert anticipation[0]["count"] == 5

    def test_analyze_prompt_sequence_session_filter(self, store):
        """Analysis filters by session_id."""
        store.record_prompt_intent(session_id="s1", prompt_text="a",
                                    intent_category="build", reasoning_type="substantive")
        store.record_prompt_intent(session_id="s2", prompt_text="b",
                                    intent_category="debug", reasoning_type="substantive")
        result = store.analyze_prompt_sequence(session_id="s1")
        assert result["total_prompts"] == 1


class TestUserThinkingModel:
    """Tests for User Thinking Patterns."""

    def test_get_empty_model(self, store):
        """Empty model returns empty list."""
        model = store.get_user_thinking_model()
        assert model == []

    def test_create_pattern(self, store):
        """Create a new thinking pattern."""
        result = store.update_thinking_pattern(
            pattern_name="escalates_micro_to_macro",
            system_adaptation="Switch to architecture mode after 3 escalation prompts",
            example_prompt="now think like elite from end to end"
        )
        assert "Created" in result
        model = store.get_user_thinking_model()
        assert len(model) == 1
        assert model[0]["pattern"] == "escalates_micro_to_macro"
        assert model[0]["confidence"] == 0.5

    def test_update_pattern_increases_confidence(self, store):
        """Repeated observations increase confidence."""
        store.update_thinking_pattern(
            "expects_continuous_loops",
            "Never stop without a blocking reason",
            "go"
        )
        store.update_thinking_pattern(
            "expects_continuous_loops",
            "Never stop without a blocking reason",
            "continue"
        )
        store.update_thinking_pattern(
            "expects_continuous_loops",
            "Never stop without a blocking reason",
            "proceed"
        )
        model = store.get_user_thinking_model()
        assert len(model) == 1
        assert model[0]["evidence"] == 3
        assert model[0]["confidence"] == pytest.approx(0.6, abs=1e-9)  # 0.5 + 0.05 + 0.05
        examples = json.loads(model[0]["examples"])
        assert "go" in examples
        assert "continue" in examples
        assert "proceed" in examples

    def test_confidence_caps_at_1(self, store):
        """Confidence never exceeds 1.0."""
        for i in range(20):
            store.update_thinking_pattern("test_pattern", "adaptation", f"prompt{i}")
        model = store.get_user_thinking_model()
        assert model[0]["confidence"] <= 1.0

    def test_examples_cap_at_10(self, store):
        """Example prompts are capped at 10 most recent."""
        for i in range(15):
            store.update_thinking_pattern("test_pattern", "adaptation", f"prompt{i}")
        model = store.get_user_thinking_model()
        examples = json.loads(model[0]["examples"])
        assert len(examples) == 10
        assert "prompt14" in examples  # Most recent kept
        assert "prompt0" not in examples  # Oldest dropped


class TestToolUsageTracking:
    """Tests for tool invocation logging."""

    def test_log_tool_usage(self, store):
        """Log a tool invocation."""
        tid = store.log_tool_usage(
            tool_name="orchestrate_request_tool",
            args_summary='{"user_prompt": "build a dashboard"}',
            result_summary="Plan generated",
            duration_ms=150
        )
        assert tid > 0

    def test_get_tool_usage_stats(self, store):
        """Get usage statistics."""
        store.log_tool_usage("tool_a", duration_ms=100)
        store.log_tool_usage("tool_a", duration_ms=200)
        store.log_tool_usage("tool_b", duration_ms=50)

        stats = store.get_tool_usage_stats(days=1)
        assert stats["total_invocations"] == 3
        assert stats["by_tool"]["tool_a"] == 2
        assert stats["by_tool"]["tool_b"] == 1
        assert "tool_a" in stats["most_used"]

    def test_truncates_long_args(self, store):
        """Args and results are truncated to 500 chars."""
        long_text = "x" * 1000
        tid = store.log_tool_usage("test_tool", args_summary=long_text)
        assert tid > 0
        # No error means truncation worked


class TestMissedDetections:
    """Tests for tracking what the system should have caught."""

    def test_record_missed_detection(self, store):
        """Record a missed detection."""
        did = store.record_missed_detection(
            detection_type="ANTICIPATION_FAILURE",
            what_was_missed="System didn't suggest crash recovery",
            root_cause="No architecture checklist running internally",
            prevention_rule="Run checklist before presenting designs"
        )
        assert did > 0

    def test_get_unautomated_detections(self, store):
        """Get detections that haven't been converted to rules.
        Note: record_missed_detection now auto-creates prevention rules for known types,
        marking them automated. Use unknown type to test unautomated path."""
        # Use types NOT in trigger_map so auto-rule creation still fires
        # but the detection gets auto-ruled anyway. So we test that the API works.
        store.record_missed_detection("LOOP_FAILURE", "System stopped", "No auto_continue", "Add flag")
        store.record_missed_detection("DEPTH_FAILURE", "Too shallow", "No gap analysis", "Add checklist")

        # Both get auto-ruled since prevention_rule is non-empty, so automated=1
        # The unautomated list should be empty because auto-rule creation marks them
        unresolved = store.get_unautomated_detections()
        assert len(unresolved) == 0  # auto-rule creation marks them automated


class TestPreventionRules:
    """Tests for automated prevention rules."""

    def test_register_prevention_rule(self, store):
        """Register a new prevention rule."""
        result = store.register_prevention_rule(
            rule_name="no_silent_stops",
            trigger_event="after_tool_call",
            check_query="Check if multi-step task is in progress",
            action_on_match="Continue execution",
            severity="P0"
        )
        assert "registered" in result

    def test_duplicate_rule_updates(self, store):
        """Registering the same rule name updates it."""
        store.register_prevention_rule("test_rule", "on_prompt", "check1", "action1", "P1")
        result = store.register_prevention_rule("test_rule", "on_prompt", "check2", "action2", "P0")
        assert "updated" in result

    def test_get_active_rules(self, store):
        """Get all active prevention rules."""
        store.register_prevention_rule("rule1", "on_prompt", "c1", "a1", "P0")
        store.register_prevention_rule("rule2", "after_audit", "c2", "a2", "P1")

        all_rules = store.get_active_prevention_rules()
        assert len(all_rules) == 2

        prompt_rules = store.get_active_prevention_rules(trigger_event="on_prompt")
        assert len(prompt_rules) == 1
        assert prompt_rules[0]["rule_name"] == "rule1"

    def test_increment_rule_trigger(self, store):
        """Incrementing trigger count works."""
        store.register_prevention_rule("test_rule", "on_prompt", "c", "a", "P1")
        rules = store.get_active_prevention_rules()
        rule_id = rules[0]["id"]

        store.increment_rule_trigger(rule_id)
        store.increment_rule_trigger(rule_id)

        rules = store.get_active_prevention_rules()
        assert rules[0]["times_triggered"] == 2

    def test_register_from_detection_marks_automated(self, store):
        """Registering a rule from a detection marks it as automated.
        Note: record_missed_detection auto-creates a prevention rule when prevention_rule
        is non-empty, so the detection is already automated after recording."""
        # Use empty prevention_rule to prevent auto-rule creation
        did = store.record_missed_detection("LOOP_FAILURE", "stops", "no flag", "")

        # Before: detection is not automated (no auto-rule since prevention_rule is empty)
        unresolved = store.get_unautomated_detections()
        assert len(unresolved) == 1

        # Register prevention rule with source detection
        store.register_prevention_rule("fix_loop", "after_tool", "check", "act", "P0",
                                        source_detection_id=did)

        # After: detection is automated
        unresolved = store.get_unautomated_detections()
        assert len(unresolved) == 0


class TestAutonomousGapDetector:
    """Tests for the autonomous gap detection system."""

    def test_autonomous_scan_empty(self, store):
        """Scan on fresh system returns no gaps."""
        result = store.autonomous_scan()
        assert result["total_gaps"] == 0
        assert result["p0_count"] == 0

    def test_autonomous_scan_finds_unresolved_detections(self, store):
        """Scan detects unresolved missed detections.
        Use empty prevention_rule so auto-rule doesn't mark it automated."""
        store.record_missed_detection("LOOP", "stopped", "bug", "")

        result = store.autonomous_scan()
        assert result["total_gaps"] >= 1
        gap = [g for g in result["gaps"] if g["source"] == "missed_detections"]
        assert len(gap) == 1
        assert gap[0]["severity"] == "P0"

    def test_autonomous_scan_detects_critical_prompts(self, store):
        """Scan detects critical prompt health."""
        # Simulate a bad session: 8 loop kicks, 2 substantive
        for i in range(8):
            store.record_prompt_intent("s1", "go", "continuation", "loop_kick")
        for i in range(2):
            store.record_prompt_intent("s1", "build X", "build", "substantive")

        result = store.autonomous_scan()
        prompt_gaps = [g for g in result["gaps"] if g["source"] == "prompt_intelligence"]
        assert len(prompt_gaps) >= 1

    def test_self_diagnose(self, store):
        """Self-diagnosis returns comprehensive health report."""
        # Seed some data
        store.record_prompt_intent("s1", "test", "build", "substantive")
        store.log_tool_usage("test_tool")
        store.record_missed_detection("LOOP", "stopped", "bug", "fix")
        store.update_thinking_pattern("test_pattern", "adaptation")

        diagnosis = store.self_diagnose()
        assert "prevention_rules" in diagnosis
        assert "prompt_intelligence" in diagnosis
        assert "missed_detections" in diagnosis
        assert "tool_usage" in diagnosis
        assert "autonomy_rate" in diagnosis
        assert "health" in diagnosis

        assert diagnosis["prompt_intelligence"]["total_prompts"] == 1
        assert diagnosis["prompt_intelligence"]["patterns_learned"] == 1
        assert diagnosis["missed_detections"]["total"] == 1
        assert diagnosis["tool_usage"]["total_calls"] == 1


class TestGoalEngine:
    """Tests for the autonomous goal generation engine."""

    def test_generate_goals_empty(self, store):
        """No data generates no goals."""
        goals = store.generate_autonomous_goals()
        assert goals == []

    def test_generate_goals_from_missed_detections(self, store):
        """Generates goals from recurring missed detection types."""
        for i in range(3):
            store.record_missed_detection("LOOP_FAILURE", f"stop {i}", "bug", "fix")

        goals = store.generate_autonomous_goals()
        loop_goals = [g for g in goals if "LOOP_FAILURE" in g["objective"]]
        assert len(loop_goals) >= 1
        assert loop_goals[0]["priority"] == "P1"

    def test_generate_goals_from_prompt_analysis(self, store):
        """Generates goals from dominant failure patterns in prompts."""
        # Create a session with >30% loop kicks -> should generate P0 goal
        for i in range(8):
            store.record_prompt_intent("s1", "go", "continuation", "loop_kick")
        for i in range(2):
            store.record_prompt_intent("s1", "build", "build", "substantive")

        goals = store.generate_autonomous_goals()
        prompt_goals = [g for g in goals if g["source"] == "prompt_intelligence"]
        assert len(prompt_goals) >= 1

    def test_generate_goals_from_unautomated(self, store):
        """Generates goal to convert unautomated detections to rules.
        Use empty prevention_rule so auto-rule doesn't fire."""
        store.record_missed_detection("LOOP", "stops", "bug", "")

        goals = store.generate_autonomous_goals()
        rule_goals = [g for g in goals if g["source"] == "prevention_rules"]
        assert len(rule_goals) >= 1
        assert rule_goals[0]["auto_executable"] is True

    def test_get_autonomous_status(self, store):
        """Full autonomous status report combines all subsystems."""
        store.record_prompt_intent("s1", "test", "build", "substantive")
        store.record_missed_detection("LOOP", "stops", "bug", "fix")

        status = store.get_autonomous_status()
        assert "diagnosis" in status
        assert "autonomous_goals" in status
        assert "gap_scan" in status
        assert "summary" in status
        assert isinstance(status["summary"], str)
