"""DeepSeek intelligence provider for article enrichment and relevance review."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class ArticleIntelligence:
    summary: str
    topics: list[str]
    sentiment: str
    importance: float
    language: str


@dataclass(frozen=True)
class LLMRelevanceAssessment:
    label: str
    confidence: float
    reason: str


class DeepSeekClient:
    name = "deepseek"

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY is not configured")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.base_url = settings.llm_base_url.rstrip("/")
        self.thinking = settings.llm_thinking

    def _chat_json(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 600,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
            "max_tokens": max_tokens,
            "temperature": 0.1,
            "thinking": {"type": self.thinking},
        }
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=90.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise ValueError("DeepSeek returned non-text content")
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I)
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("DeepSeek returned a non-object JSON response")
        return parsed

    def enrich_article(self, *, title: str, body: str, language: str) -> ArticleIntelligence:
        result = self._chat_json(
            system=(
                "You are an editor for a Kuwait media-intelligence platform. "
                "Return strict JSON only. Do not invent facts. "
                "Summarize only the supplied article. "
                "Use the article's language for the summary and topic labels."
            ),
            user=(
                "Analyze this article and return exactly: "
                '{"summary":"1-2 concise sentences","topics":["up to 5 short labels"],'
                '"sentiment":"positive|neutral|negative|mixed",'
                '"importance":0.0,"language":"ar|en"}. '
                "Importance means likely significance to a professional monitoring client, "
                "from 0 to 1.\n\n"
                f"Declared language: {language}\nTitle: {title}\nArticle:\n{body[:14000]}"
            ),
            max_tokens=700,
        )
        topics = result.get("topics")
        if not isinstance(topics, list):
            topics = []
        clean_topics = [str(topic).strip()[:80] for topic in topics if str(topic).strip()][:5]
        sentiment = str(result.get("sentiment") or "neutral").lower()
        if sentiment not in {"positive", "neutral", "negative", "mixed"}:
            sentiment = "neutral"
        try:
            importance = max(0.0, min(1.0, float(result.get("importance", 0.5))))
        except (TypeError, ValueError):
            importance = 0.5
        detected_language = str(result.get("language") or language).lower()
        if detected_language not in {"ar", "en"}:
            detected_language = language if language in {"ar", "en"} else "ar"
        return ArticleIntelligence(
            summary=str(result.get("summary") or "").strip()[:1200],
            topics=clean_topics,
            sentiment=sentiment,
            importance=importance,
            language=detected_language,
        )

    def assess_relevance(
        self,
        *,
        entity_query: str,
        article_title: str,
        article_body: str,
    ) -> LLMRelevanceAssessment:
        result = self._chat_json(
            system=(
                "You review ambiguous media-monitoring matches. Return strict JSON only. "
                "Judge whether the supplied article is meaningfully about the monitored entity. "
                "Namesakes and incidental mentions are not relevant. Never invent evidence."
            ),
            user=(
                "Return exactly: "
                '{"label":"relevant|not_relevant|needs_review","confidence":0.0,'
                '"reason":"one concise evidence-based sentence"}.\n\n'
                f"Monitored entity and instructions: {entity_query}\n"
                f"Article title: {article_title}\n"
                f"Article body:\n{article_body[:12000]}"
            ),
            max_tokens=350,
        )
        label = str(result.get("label") or "needs_review")
        if label not in {"relevant", "not_relevant", "needs_review"}:
            label = "needs_review"
        try:
            confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
        except (TypeError, ValueError):
            confidence = 0.5
        return LLMRelevanceAssessment(
            label=label,
            confidence=confidence,
            reason=str(result.get("reason") or "DeepSeek returned no reason.")[:1000],
        )


def get_llm_client(settings: Settings | None = None) -> DeepSeekClient | None:
    settings = settings or get_settings()
    if settings.llm_provider != "deepseek" or not settings.llm_api_key:
        return None
    return DeepSeekClient(settings)
