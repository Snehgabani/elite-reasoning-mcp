import pytest
from core.verification.registry import SyntaxVerifier, VerifierContext, VerifierRequest


@pytest.mark.asyncio
async def test_syntax_verifier_markdown_inference():
    verifier = SyntaxVerifier()
    md_content = """# System Architecture Overview
- Component 1: In-memory store
- Component 2: Background watcher
## Deployment Steps
1. Install dependencies
2. Run service
"""
    req = VerifierRequest(check="syntax", draft=md_content)
    res = await verifier.verify(req, VerifierContext(store=None))

    assert res.status.value == "PASS"
    assert res.subject_kind == "source:markdown"
    assert res.data.get("passed") is True


@pytest.mark.asyncio
async def test_syntax_verifier_json_inference():
    verifier = SyntaxVerifier()
    json_content = '{\n  "name": "elite-system",\n  "active": true\n}'
    req = VerifierRequest(check="syntax", code=json_content)
    res = await verifier.verify(req, VerifierContext(store=None))

    assert res.status.value == "PASS"
    assert res.subject_kind == "source:json"
    assert res.data.get("passed") is True
