"""Tests for the Goal-Aligned Prompt Polisher."""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.tools.goal_prompt_polisher import GoalPromptPolisher, PolishResult


class MockStore:
    """Minimal mock of EliteStore for testing."""

    def __init__(self, goals=None):
        self._goals = goals or []

    def get_active_goals(self):
        return self._goals

    def record_prompt_intent(self, **kwargs):
        return 1

    def analyze_prompt_sequence(self, **kwargs):
        return {"prompts": [], "patterns": []}


class TestPromptScoring:
    """Test the prompt quality scoring system."""

    def test_empty_prompt_scores_zero(self):
        polisher = GoalPromptPolisher(MockStore())
        assert polisher.score_prompt("") == 0
        assert polisher.score_prompt(None) == 0

    def test_short_prompt_gets_base_score(self):
        polisher = GoalPromptPolisher(MockStore())
        score = polisher.score_prompt("fix bug")
        assert 30 <= score <= 45  # Base + maybe a signal or two

    def test_specific_prompt_scores_higher(self):
        polisher = GoalPromptPolisher(MockStore())
        vague = polisher.score_prompt("fix the thing")
        specific = polisher.score_prompt(
            "fix the login bug: users get a 403 error when trying to "
            "verify their email token. Check the auth middleware for "
            "edge cases in token validation."
        )
        assert specific > vague

    def test_quality_signals_boost_score(self):
        polisher = GoalPromptPolisher(MockStore())
        base = polisher.score_prompt("build a feature")
        with_signals = polisher.score_prompt(
            "build a feature with specific constraints, "
            "validate edge cases, measure performance, "
            "step by step verify the security"
        )
        assert with_signals > base
        assert with_signals >= 60  # Should be well above base

    def test_score_capped_at_100(self):
        polisher = GoalPromptPolisher(MockStore())
        mega_prompt = (
            "Specifically verify and validate the edge case handling "
            "step by step. Measure the benchmark metric for security "
            "vulnerability performance. Document the rationale because "
            "of the trade-off. Check the constraint requirement. "
        ) * 3
        score = polisher.score_prompt(mega_prompt)
        assert score <= 100

    def test_code_context_boosts_score(self):
        polisher = GoalPromptPolisher(MockStore())
        without = polisher.score_prompt("fix the auth issue")
        with_context = polisher.score_prompt("fix the auth issue in `core/middleware/auth.py` file")
        assert with_context > without

    def test_structured_prompt_scores_higher(self):
        polisher = GoalPromptPolisher(MockStore())
        flat = polisher.score_prompt("do several things and make them work")
        structured = polisher.score_prompt(
            "1. First, check the database\n2. Then validate the schema\n3. Finally, run the migration"
        )
        assert structured > flat


class TestIntentClassification:
    """Test prompt intent classification."""

    def test_debug_intent(self):
        polisher = GoalPromptPolisher(MockStore())
        assert polisher._classify_intent("fix the broken login bug") == "debug"

    def test_build_intent(self):
        polisher = GoalPromptPolisher(MockStore())
        assert polisher._classify_intent("create a new user dashboard") == "build"

    def test_deploy_intent(self):
        polisher = GoalPromptPolisher(MockStore())
        assert polisher._classify_intent("deploy to production and ship the release") == "deploy"

    def test_design_intent(self):
        polisher = GoalPromptPolisher(MockStore())
        assert polisher._classify_intent("design the architecture for the new system") == "design"

    def test_general_intent_fallback(self):
        polisher = GoalPromptPolisher(MockStore())
        assert polisher._classify_intent("hello world") == "general"


class TestComplexityClassification:
    """Test prompt complexity scoring."""

    def test_simple_prompt_low_complexity(self):
        polisher = GoalPromptPolisher(MockStore())
        complexity = polisher._classify_complexity("fix bug", "debug")
        assert complexity <= 2

    def test_long_prompt_higher_complexity(self):
        polisher = GoalPromptPolisher(MockStore())
        long_prompt = " ".join(["word"] * 50)
        complexity = polisher._classify_complexity(long_prompt, "build")
        assert complexity >= 3

    def test_technical_prompt_higher_complexity(self):
        polisher = GoalPromptPolisher(MockStore())
        technical = (
            "Set up the database migration for the microservice with API authentication and deploy to kubernetes"
        )
        complexity = polisher._classify_complexity(technical, "deploy")
        assert complexity >= 3


class TestGoalAlignment:
    """Test goal context building and alignment."""

    def test_no_goals_returns_empty(self):
        polisher = GoalPromptPolisher(MockStore(goals=[]))
        context, aligned = polisher._build_goal_context([], "test prompt", "build")
        assert context == ""
        assert aligned == []

    def test_relevant_goal_is_aligned(self):
        goals = [
            {
                "id": 1,
                "objective": "Improve login performance and fix auth bugs",
                "key_results": ["Reduce login latency to <200ms", "Fix all auth bugs"],
                "overall_pct": 30,
                "progress": {},
            }
        ]
        polisher = GoalPromptPolisher(MockStore(goals=goals))
        context, aligned = polisher._build_goal_context(goals, "fix the login auth bug", "debug")
        assert len(aligned) >= 1
        assert "login" in aligned[0].lower() or "auth" in aligned[0].lower()
        assert "GOAL" in context or "FOCUS" in context

    def test_irrelevant_goal_falls_back_to_latest(self):
        goals = [
            {
                "id": 1,
                "objective": "Redesign the payment system",
                "key_results": ["New Stripe integration"],
                "overall_pct": 50,
                "progress": {},
            }
        ]
        polisher = GoalPromptPolisher(MockStore(goals=goals))
        context, aligned = polisher._build_goal_context(goals, "fix the weather API", "debug")
        # Should still inject the latest goal as general context
        assert len(aligned) >= 1
        assert context  # Non-empty


class TestFullPolish:
    """Test the complete polish pipeline."""

    def test_empty_prompt_passthrough(self):
        polisher = GoalPromptPolisher(MockStore())
        result = polisher.polish("")
        assert result.original_score == 0
        assert result.polished_score == 0
        assert result.polished_prompt == ""

    def test_polish_improves_score(self):
        polisher = GoalPromptPolisher(MockStore())
        result = polisher.polish("fix the login bug")
        assert result.polished_score > result.original_score
        assert len(result.enhancements_applied) > 0

    def test_polish_adds_quality_directives(self):
        polisher = GoalPromptPolisher(MockStore())
        result = polisher.polish("build a new user dashboard")
        assert "Quality Directives" in result.polished_prompt
        assert "Output Standard" in result.polished_prompt

    def test_polish_injects_goal_context(self):
        goals = [
            {
                "id": 1,
                "objective": "Ship the dashboard feature by Friday",
                "key_results": ["Complete UI", "Add tests", "Deploy to staging"],
                "overall_pct": 40,
                "progress": {},
            }
        ]
        polisher = GoalPromptPolisher(MockStore(goals=goals))
        result = polisher.polish("build the dashboard components")
        assert result.goal_context_injected is True
        assert len(result.goals_aligned) >= 1
        assert "Goal Alignment" in result.polished_prompt

    def test_polish_result_has_all_fields(self):
        polisher = GoalPromptPolisher(MockStore())
        result = polisher.polish("create a REST API with authentication")
        assert isinstance(result, PolishResult)
        assert result.original_prompt == "create a REST API with authentication"
        assert result.polished_prompt != ""
        assert 0 <= result.original_score <= 100
        assert 0 <= result.polished_score <= 100
        assert result.complexity >= 1
        assert result.intent in (
            "build",
            "debug",
            "deploy",
            "design",
            "refactor",
            "investigate",
            "test",
            "optimize",
            "audit",
            "general",
        )

    def test_complex_prompt_gets_deeper_directives(self):
        polisher = GoalPromptPolisher(MockStore())
        simple_result = polisher.polish("fix typo")
        complex_result = polisher.polish(
            "Redesign the entire authentication system to support "
            "OAuth2, SAML, and passwordless login. The new system "
            "must handle the API gateway integration and also "
            "support the microservice architecture with distributed "
            "session management and additionally implement rate limiting."
        )
        assert complex_result.complexity > simple_result.complexity
        assert len(complex_result.enhancements_applied) >= len(simple_result.enhancements_applied)

    def test_security_aware_prompt_gets_security_gates(self):
        polisher = GoalPromptPolisher(MockStore())
        result = polisher.polish("build a user input form with database API endpoint")
        assert any("security" in e for e in result.enhancements_applied)


class TestIntentGates:
    """Test intent-specific quality gates."""

    def test_debug_gates(self):
        polisher = GoalPromptPolisher(MockStore())
        gates = polisher._get_intent_gates("debug")
        assert len(gates) >= 2
        assert any("ROOT CAUSE" in g for g in gates)

    def test_build_gates(self):
        polisher = GoalPromptPolisher(MockStore())
        gates = polisher._get_intent_gates("build")
        assert len(gates) >= 2
        assert any("adopt" in g.lower() or "library" in g.lower() for g in gates)

    def test_deploy_gates(self):
        polisher = GoalPromptPolisher(MockStore())
        gates = polisher._get_intent_gates("deploy")
        assert len(gates) >= 2
        assert any("rollback" in g.lower() for g in gates)

    def test_general_returns_empty(self):
        polisher = GoalPromptPolisher(MockStore())
        gates = polisher._get_intent_gates("general")
        assert gates == []


class TestQualityBar:
    """Test quality bar generation."""

    def test_low_complexity_simple_bar(self):
        polisher = GoalPromptPolisher(MockStore())
        bar = polisher._get_quality_bar(1)
        assert "clean" in bar.lower() or "working" in bar.lower()

    def test_high_complexity_detailed_bar(self):
        polisher = GoalPromptPolisher(MockStore())
        bar = polisher._get_quality_bar(5)
        assert "verification" in bar.lower()
        assert "pre-mortem" in bar.lower()
        assert "rollback" in bar.lower()
