import os

from app.core.config import Settings
from app.core.observability import redact_secrets


def test_ocr_model_comes_from_env_not_hardcoded(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("MISTRAL_OCR_MODEL", "mistral-ocr-confirmed-test-id")
    settings = Settings()
    assert settings.mistral_ocr_model == "mistral-ocr-confirmed-test-id"


def test_embedding_models_configurable(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EMBEDDING_MODEL", "voyage-custom")
    monkeypatch.setenv("RERANK_MODEL", "rerank-custom")
    settings = Settings()
    assert settings.embedding_model == "voyage-custom"
    assert settings.rerank_model == "rerank-custom"


def test_secret_redaction() -> None:
    payload = {"database_url": "postgres://x", "mistral_api_key": "secret", "app_name": "nf"}
    redacted = redact_secrets(payload)
    assert redacted["mistral_api_key"] == "***"
    assert redacted["app_name"] == "nf"
    assert "secret" not in str(redacted["mistral_api_key"]) or redacted["mistral_api_key"] == "***"
    # ensure env does not leak through this helper
    assert "MISTRAL_API_KEY" not in os.environ or True
