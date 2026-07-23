from unittest.mock import MagicMock

from app.core.config import Settings
from app.services.llm import DeepSeekClient


def test_deepseek_article_enrichment_parses_strict_json(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    response = MagicMock()
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"summary":"ملخص موجز","topics":["الكويت","اقتصاد"],'
                        '"sentiment":"neutral","importance":0.8,"language":"ar"}'
                    )
                }
            }
        ]
    }
    monkeypatch.setattr("app.services.llm.httpx.post", lambda *args, **kwargs: response)
    settings = Settings(
        llm_provider="deepseek",
        llm_api_key="test-key",
        llm_model="deepseek-v4-flash",
    )
    result = DeepSeekClient(settings).enrich_article(
        title="عنوان",
        body="نص الخبر",
        language="ar",
    )
    assert result.summary == "ملخص موجز"
    assert result.topics == ["الكويت", "اقتصاد"]
    assert result.importance == 0.8
    response.raise_for_status.assert_called_once()


def test_deepseek_relevance_never_accepts_unknown_label(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    response = MagicMock()
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"label":"maybe","confidence":4,"reason":"uncertain"}'
                }
            }
        ]
    }
    monkeypatch.setattr("app.services.llm.httpx.post", lambda *args, **kwargs: response)
    client = DeepSeekClient(
        Settings(llm_provider="deepseek", llm_api_key="test-key")
    )
    result = client.assess_relevance(
        entity_query="Example Co",
        article_title="Headline",
        article_body="Body",
    )
    assert result.label == "needs_review"
    assert result.confidence == 1.0
