from dataclasses import dataclass

import pytest

from core.verification.models import VerificationStatus
from core.verification.registry import (
    VerificationExecution,
    VerificationInputError,
    VerifierContext,
    VerifierRegistry,
    VerifierRequest,
    build_core_verifier_registry,
)


@dataclass
class _DummyVerifier:
    name: str = "dummy"

    async def verify(self, request: VerifierRequest, context: VerifierContext) -> VerificationExecution:
        return VerificationExecution(
            check=self.name,
            status=VerificationStatus.PASS,
            data={"value": request.query},
            subject_kind="query",
            subject=request.query,
            producer="tests.dummy",
            evidence_payload={"value": request.query},
        )


@pytest.mark.asyncio
async def test_registry_dispatches_by_declared_name():
    registry = VerifierRegistry(VerifierContext(store=object()))
    registry.register(_DummyVerifier())

    result = await registry.verify(VerifierRequest(check="DUMMY", query="observed"))
    assert result.status is VerificationStatus.PASS
    assert result.data == {"value": "observed"}
    assert registry.names() == ("dummy",)


def test_registry_rejects_duplicate_and_unknown_verifiers():
    registry = VerifierRegistry(VerifierContext(store=object()))
    registry.register(_DummyVerifier())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_DummyVerifier())

    with pytest.raises(VerificationInputError, match="unsupported verification check"):
        import asyncio

        asyncio.run(registry.verify(VerifierRequest(check="missing")))


def test_core_registry_has_one_inspectable_entry_per_public_check(tmp_path):
    class _Store:
        pass

    registry = build_core_verifier_registry(_Store())
    assert registry.names() == (
        "cegis",
        "constraints",
        "diagnostics",
        "diff",
        "evidence",
        "grounding",
        "outcomes",
        "syntax",
        "tests",
        "types",
    )
