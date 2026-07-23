from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class ConnectorType(StrEnum):
    rss = "rss"
    sitemap = "sitemap"
    html = "html"
    licensed_api = "licensed_api"
    browser = "browser"
    epaper = "epaper"
    pending = "pending"
    blocked = "blocked"


class DiscoveredItem(BaseModel):
    """Canonical discovery record before full article fetch/parse."""

    source_url: str
    canonical_url: str | None = None
    title: str | None = None
    published_at: str | None = None
    summary: str | None = None
    language: Literal["ar", "en"] | None = None
    content_hash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConnectorContext(BaseModel):
    publisher_code: str
    channel_code: str
    base_url: HttpUrl | str
    language: Literal["ar", "en"]
    config: dict[str, Any] = Field(default_factory=dict)
    politeness_delay_ms: int = 1000
    max_requests_per_minute: int = 10
    user_agent: str = "NewsFetcherBot/0.1 (+https://newsfetcher.local; media-monitoring; contact=ops@newsfetcher.local)"


class ConnectorResult(BaseModel):
    connector_type: ConnectorType
    items: list[DiscoveredItem] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
