"""Rerank providers (Voyage preferred; local lexical overlap fallback)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.core.arabic import normalize_text
from app.core.config import Settings, get_settings
from app.services.embeddings import cosine_similarity


@dataclass
class RerankItem:
    index: int
    score: float


class RerankProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def rerank(self, query: str, documents: list[str], *, top_k: int) -> list[RerankItem]:
        raise NotImplementedError


class LocalRerankProvider(RerankProvider):
    name = "local"

    def __init__(self, model: str = "local-overlap-v1") -> None:
        self.model = model

    def rerank(self, query: str, documents: list[str], *, top_k: int) -> list[RerankItem]:
        q_tokens = set(normalize_text(query).split())
        scored: list[RerankItem] = []
        for idx, doc in enumerate(documents):
            d_tokens = set(normalize_text(doc).split())
            if not q_tokens or not d_tokens:
                score = 0.0
            else:
                overlap = len(q_tokens & d_tokens) / len(q_tokens)
                # blend light length-normalized cosine-like score via token sets
                score = overlap
            scored.append(RerankItem(index=idx, score=score))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]


class VoyageRerankProvider(RerankProvider):
    name = "voyage"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def rerank(self, query: str, documents: list[str], *, top_k: int) -> list[RerankItem]:
        response = httpx.post(
            "https://api.voyageai.com/v1/rerank",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "query": query,
                "documents": documents,
                "top_k": top_k,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        rows = response.json().get("data", [])
        return [
            RerankItem(index=int(row["index"]), score=float(row["relevance_score"]))
            for row in rows
        ]


def get_rerank_provider(settings: Settings | None = None) -> RerankProvider:
    settings = settings or get_settings()
    if settings.rerank_provider == "voyage" and settings.voyage_api_key:
        return VoyageRerankProvider(api_key=settings.voyage_api_key, model=settings.rerank_model)
    if settings.embedding_fallback_local or settings.rerank_provider == "local":
        return LocalRerankProvider()
    raise RuntimeError("No rerank provider available. Set VOYAGE_API_KEY or use local fallback.")


def blend_scores(vector_sim: float, rerank_score: float | None) -> float:
    if rerank_score is None:
        return vector_sim
    return (0.55 * vector_sim) + (0.45 * rerank_score)


# re-export for callers that combine embedding similarity with rerank
__all__ = [
    "LocalRerankProvider",
    "RerankItem",
    "RerankProvider",
    "VoyageRerankProvider",
    "blend_scores",
    "cosine_similarity",
    "get_rerank_provider",
]
