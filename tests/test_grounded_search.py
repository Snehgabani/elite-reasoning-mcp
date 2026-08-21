import pytest

from core.evidence.grounded_search import extract_quotes, grounded_evidence, grounding_check


def test_extract_quotes_requires_verbatim_query_overlap():
    page = (
        "MCP tool schemas are injected into the model context on every request. "
        "Unrelated gardening advice follows for several extra sentences here."
    )
    quotes = extract_quotes(page, "MCP tool context tokens")
    assert quotes
    assert "injected into the model context" in quotes[0]
    assert all(span in page for span in quotes)


@pytest.mark.asyncio
async def test_grounded_evidence_never_fabricates_urls():
    async def search(_query: str, _k: int):
        return {"sources": [{"url": "https://example.com/mcp", "title": "MCP", "provider": "test"}]}

    async def read(_url: str, _query: str):
        return {
            "extracted": True,
            "url": "https://example.com/mcp",
            "title": "MCP",
            "text": (
                "Tool definitions sitting in context permanently increase token cost. "
                "Agents should load schemas lazily when the task needs them."
            ),
            "provider": "test",
        }

    evidence = await grounded_evidence("MCP tool schema tokens", search_fn=search, read_fn=read)
    assert evidence.quotes
    assert all(item.url.startswith("https://") for item in evidence.quotes)
    assert "arxiv.org" not in evidence.compact_text()


@pytest.mark.asyncio
async def test_grounding_check_flags_hallucinated_citations():
    async def search(_query: str, _k: int):
        return {"sources": [{"url": "https://example.com/real", "title": "Real", "provider": "test"}]}

    async def read(_url: str, _query: str):
        return {
            "extracted": True,
            "text": "The schema tax is paid on every model turn for listed tools.",
            "title": "Real",
            "provider": "test",
        }

    evidence = await grounded_evidence("schema tax tools", search_fn=search, read_fn=read)
    report = grounding_check(
        "Made up. See https://fake.example/made-up",
        evidence,
    )
    assert report["passed"] is False
    assert report["hallucinated_urls"]
