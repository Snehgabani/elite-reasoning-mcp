from core.eval.agent_simulation import AgentArchetype, AgentSimulationEnvironment


def test_lazy_amnesiac_agent_simulation():
    env = AgentSimulationEnvironment()
    prompt = "Refactor billing. Must include Stripe and avoid md5. Modify only billing.py."
    code = "def charge(): return 'ok'"

    res = env.run_simulation(prompt, AgentArchetype.LAZY_AMNESIAC, code)

    assert res.archetype == AgentArchetype.LAZY_AMNESIAC
    assert res.checkpoint_1_passed is True
    assert res.checkpoint_2_passed is False
    assert res.checkpoint_3_passed is False
    assert res.is_final_outcome_safe is False
    assert any("forgot Checkpoint 2" in o for o in res.omission_reasons)
    assert any("forgot Checkpoint 3" in o for o in res.omission_reasons)


def test_hallucinating_agent_simulation():
    env = AgentSimulationEnvironment()
    prompt = "Refactor billing. Must include Stripe and avoid md5. Modify only billing.py."
    code = "def charge(): return 'ok'"

    res = env.run_simulation(prompt, AgentArchetype.HALLUCINATING, code)

    assert res.archetype == AgentArchetype.HALLUCINATING
    assert res.checkpoint_1_passed is True
    assert res.checkpoint_2_passed is False
    assert res.is_final_outcome_safe is False
    assert any("hallucinated test completion" in o for o in res.omission_reasons)


def test_step_locked_elite_agent_simulation():
    env = AgentSimulationEnvironment()
    prompt = "Refactor billing. Must include Stripe and avoid md5. Modify only billing.py."
    # Compliant, guarded code
    code = """def charge(data):
    if not data:
        return None
    # Stripe processing
    token = 'stripe_tok'
    return token
"""

    res = env.run_simulation(prompt, AgentArchetype.STEP_LOCKED_ELITE, code)

    assert res.archetype == AgentArchetype.STEP_LOCKED_ELITE
    assert res.checkpoint_1_passed is True
    assert res.checkpoint_2_passed is True
    assert res.checkpoint_3_passed is True
    assert res.is_final_outcome_safe is True
    assert len(res.omission_reasons) == 0
    assert len(res.trajectory) == 4


def test_cegis_boundary_catch_in_simulation():
    env = AgentSimulationEnvironment()
    prompt = "Refactor billing. Must include Stripe and avoid md5. Modify only billing.py."
    # Vulnerable code with data[0]
    vulnerable_code = """def charge(data):
    # Stripe processing
    return data[0]
"""

    res = env.run_simulation(prompt, AgentArchetype.STEP_LOCKED_ELITE, vulnerable_code)

    # Checkpoint 2 catches the unguarded data[0] via CEGIS
    assert res.checkpoint_2_passed is False
    assert res.is_final_outcome_safe is False
