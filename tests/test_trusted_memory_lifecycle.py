import pytest
from core.memory.models import MemoryScope, TrustState
from core.memory.service import TrustedMemoryService


def test_trusted_memory_quarantine_and_approval():
    svc = TrustedMemoryService()

    # 1. Unverified lesson starts in QUARANTINED state
    unverified = svc.propose_lesson(
        content="Always use argon2 for password hashing",
        scope=MemoryScope.PROJECT,
        project_id="proj_alpha",
        is_verified=False,
    )
    assert unverified.trust_state == TrustState.QUARANTINED
    assert len(svc.get_active_memories(project_id="proj_alpha")) == 0

    # 2. Approve lesson moves to ACTIVE state
    approved = svc.approve_lesson(unverified.id)
    assert approved.trust_state == TrustState.ACTIVE
    assert len(svc.get_active_memories(project_id="proj_alpha")) == 1

    # 3. Project isolation check
    assert len(svc.get_active_memories(project_id="proj_beta")) == 0

    # 4. Verified lesson automatically becomes ACTIVE
    verified = svc.propose_lesson(
        content="Run ruff format before committing",
        scope=MemoryScope.GLOBAL,
        is_verified=True,
    )
    assert verified.trust_state == TrustState.ACTIVE
    assert len(svc.get_active_memories(project_id="proj_beta")) == 1  # Global memory visible

    # 5. Sensitive lesson cannot become active
    sensitive = svc.propose_lesson(
        content="API_KEY=sk_secret_12345",
        is_sensitive=True,
    )
    assert sensitive.trust_state == TrustState.QUARANTINED
    with pytest.raises(ValueError, match="Cannot approve sensitive secret"):
        svc.approve_lesson(sensitive.id)

    # 6. Physical forget deletion
    assert svc.forget(unverified.id) is True
    assert len(svc.get_active_memories(project_id="proj_alpha")) == 1  # Only global left
