"""Embedding providers.

Voyage is preferred when VOYAGE_API_KEY is set.
Otherwise a local deterministic hasher is used for tests/dev (never for production claims).
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import Settings, get_settings

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


class EmbeddingProvider(ABC):
    name: str
    model: str
    dimensions: int

    @abstractmethod
    def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]:
        raise NotImplementedError


class LocalHashEmbeddingProvider(EmbeddingProvider):
    """Deterministic bag-of-tokens hashing into a fixed vector space."""

    name = "local"

    def __init__(self, model: str = "local-hash-v1", dimensions: int = 1024) -> None:
        self.model = model
        self.dimensions = dimensions

    def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]:
        _ = input_type
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        tokens = _TOKEN_RE.findall(text.lower())
        if not tokens:
            tokens = ["empty"]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class VoyageEmbeddingProvider(EmbeddingProvider):
    name = "voyage"

    def __init__(self, api_key: str, model: str, dimensions: int) -> None:
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions

    def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]:
        if not texts:
            return []
        payload: dict[str, Any] = {
            "model": self.model,
            "input": texts,
            "input_type": input_type,
        }
        # Some Voyage models accept output_dimension; only send when configured.
        if self.dimensions:
            payload["output_dimension"] = self.dimensions
        response = httpx.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()["data"]
        data_sorted = sorted(data, key=lambda row: row["index"])
        vectors = [row["embedding"] for row in data_sorted]
        if vectors and len(vectors[0]) != self.dimensions:
            raise ValueError(
                f"Voyage returned dim={len(vectors[0])} but configured dim={self.dimensions}"
            )
        return vectors


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    settings = settings or get_settings()
    if settings.embedding_provider == "voyage" and settings.voyage_api_key:
        return VoyageEmbeddingProvider(
            api_key=settings.voyage_api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )
    if settings.embedding_fallback_local or settings.embedding_provider == "local":
        return LocalHashEmbeddingProvider(
            model="local-hash-v1",
            dimensions=settings.embedding_dimensions,
        )
    raise RuntimeError(
        "No embedding provider available. Set VOYAGE_API_KEY or EMBEDDING_PROVIDER=local."
    )


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("vector length mismatch")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
