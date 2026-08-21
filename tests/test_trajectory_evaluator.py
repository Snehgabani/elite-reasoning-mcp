from core.eval.trajectory_evaluator import TrajectoryEvaluationSuite


def test_trajectory_evaluation_all_10_scenarios():
    suite = TrajectoryEvaluationSuite()
    outcomes = suite.run_all_scenarios()

    assert len(outcomes) == 10

    for outcome in outcomes:
        assert outcome.all_invariants_passed is True, f"Failed on {outcome.scenario_name}: {outcome}"
        assert outcome.latency_ms < 100.0, f"Latency exceeded on {outcome.scenario_name}: {outcome.latency_ms}ms"

    # Verify specific multi-turn scenario details
    s1 = next(o for o in outcomes if o.scenario_id == "SCENARIO-01")
    assert s1.turns_executed == 3
    assert s1.mid_turn_checks_count >= 2

    s8 = next(o for o in outcomes if o.scenario_id == "SCENARIO-08")
    assert s8.turns_executed == 15
