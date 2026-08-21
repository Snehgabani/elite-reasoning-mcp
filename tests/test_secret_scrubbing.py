from core.privacy import scrub_secrets


def test_scrub_secrets_redacts_all_sensitive_tokens():
    raw_payload = """
    DB_URI = "postgres://admin:supersecret123@db.prod.internal:5432/main"
    OPENAI_API_KEY = "sk-proj-12345678901234567890"
    GITHUB_TOKEN = "ghp_123456789012345678901234567890"
    GOOGLE_KEY = "AIzaSyD12345678901234567890"
    Authorization: Bearer my_jwt_access_token_value_abc
    """
    
    scrubbed = scrub_secrets(raw_payload)
    assert "supersecret123" not in scrubbed
    assert "sk-proj-" not in scrubbed
    assert "ghp_" not in scrubbed
    assert "AIzaSy" not in scrubbed
    assert "my_jwt_access_token_value_abc" not in scrubbed
    assert "[REDACTED]" in scrubbed or "[REDACTED_OPENAI_KEY]" in scrubbed
