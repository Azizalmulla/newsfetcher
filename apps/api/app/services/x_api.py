"""Official X API client.

Never scrapes the public web. Live HTTP calls require every Phase 10 gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class XPostPayload:
    external_post_id: str
    text: str
    posted_at: datetime | None
    language: str | None
    permalink: str | None
    raw: dict[str, Any]


class XTimelineClient(Protocol):
    def fetch_user_timeline(self, *, handle: str, max_results: int = 10) -> list[XPostPayload]:
        ...


class GatedXApiClient:
    """Official API client that refuses to call unless gates + secrets are set."""

    def __init__(self, settings: Settings, *, gates_ok: bool) -> None:
        self.settings = settings
        self.gates_ok = gates_ok

    def fetch_user_timeline(self, *, handle: str, max_results: int = 10) -> list[XPostPayload]:
        if not self.gates_ok:
            raise PermissionError(
                "x_api_gates_incomplete: credentials/pricing/endpoints/terms/cost/live"
            )
        if not self.settings.x_api_live_enabled:
            raise PermissionError("x_api_live_disabled")
        if not self.settings.x_api_bearer_token:
            raise PermissionError("x_api_bearer_missing")
        if not self.settings.x_api_base_url:
            raise PermissionError("x_api_base_url_missing")

        # User timeline by username — path must match pinned official docs.
        # Default shape follows X API v2 recent tweets-by-username pattern.
        url = (
            f"{self.settings.x_api_base_url.rstrip('/')}"
            f"/users/by/username/{handle.lstrip('@')}/tweets"
        )
        headers = {"Authorization": f"Bearer {self.settings.x_api_bearer_token}"}
        params = {
            "max_results": str(max(5, min(max_results, 100))),
            "tweet.fields": "created_at,lang,text",
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

        posts: list[XPostPayload] = []
        for item in data.get("data") or []:
            created = item.get("created_at")
            posted_at = None
            if created:
                posted_at = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            post_id = str(item.get("id"))
            posts.append(
                XPostPayload(
                    external_post_id=post_id,
                    text=str(item.get("text") or ""),
                    posted_at=posted_at,
                    language=item.get("lang"),
                    permalink=f"https://x.com/{handle.lstrip('@')}/status/{post_id}",
                    raw=item if isinstance(item, dict) else {"item": item},
                )
            )
        return posts


class FixtureXClient:
    """Deterministic offline posts for tests — not a scrape."""

    def __init__(self, posts_by_handle: dict[str, list[XPostPayload]] | None = None) -> None:
        self.posts_by_handle = posts_by_handle or {}

    def fetch_user_timeline(self, *, handle: str, max_results: int = 10) -> list[XPostPayload]:
        key = handle.lstrip("@").lower()
        rows = self.posts_by_handle.get(key, [])
        return rows[:max_results]


def build_x_client(*, gates_ok: bool, settings: Settings | None = None) -> XTimelineClient:
    cfg = settings or get_settings()
    if cfg.x_api_mode == "fixture":
        # Empty fixture client — callers inject posts via social.ingest_fixture_posts.
        return FixtureXClient()
    return GatedXApiClient(cfg, gates_ok=gates_ok)


def sample_fixture_post(handle: str, text: str, external_id: str) -> XPostPayload:
    return XPostPayload(
        external_post_id=external_id,
        text=text,
        posted_at=datetime.now(UTC),
        language="en",
        permalink=f"https://x.com/{handle.lstrip('@')}/status/{external_id}",
        raw={"fixture": True, "handle": handle},
    )
