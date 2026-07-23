from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import feedparser

from newsfetcher_connectors.base import SourceConnector
from newsfetcher_connectors.types import (
    ConnectorContext,
    ConnectorResult,
    ConnectorType,
    DiscoveredItem,
)


def _entry_published_at(entry: object) -> datetime | None:
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(str(raw))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except (TypeError, ValueError, IndexError):
            pass
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except ValueError:
            continue
    return None


class RssConnector(SourceConnector):
    connector_type = ConnectorType.rss

    def discover(self, context: ConnectorContext) -> ConnectorResult:
        feed_urls = context.config.get("feed_urls") or []
        if not feed_urls:
            feed_urls = self._default_feed_candidates(str(context.base_url))

        lookback_days = context.config.get("lookback_days")
        cutoff = None
        if lookback_days is not None:
            cutoff = datetime.now(UTC) - timedelta(days=int(lookback_days))

        client = self._http(context)
        owns_client = self._client is None
        items: list[DiscoveredItem] = []
        errors: list[str] = []
        skipped_stale = 0
        meta: dict[str, object] = {
            "feeds_tried": [],
            "feeds_ok": [],
            "lookback_days": lookback_days,
            "skipped_stale": 0,
        }

        try:
            for feed_url in feed_urls:
                meta["feeds_tried"].append(feed_url)  # type: ignore[index]
                try:
                    response = client.get(feed_url)
                    if response.status_code >= 400:
                        errors.append(f"{feed_url} -> HTTP {response.status_code}")
                        continue
                    parsed = feedparser.parse(response.content)
                    if getattr(parsed, "bozo", False) and not parsed.entries:
                        errors.append(f"{feed_url} -> invalid feed: {parsed.bozo_exception}")
                        continue
                    meta["feeds_ok"].append(feed_url)  # type: ignore[index]
                    for entry in parsed.entries:
                        link = getattr(entry, "link", None) or ""
                        if not link:
                            continue
                        published_at = _entry_published_at(entry)
                        if cutoff is not None and published_at is not None and published_at < cutoff:
                            skipped_stale += 1
                            continue
                        items.append(
                            DiscoveredItem(
                                source_url=link,
                                canonical_url=link,
                                title=getattr(entry, "title", None),
                                published_at=published_at.isoformat() if published_at else (
                                    getattr(entry, "published", None)
                                    or getattr(entry, "updated", None)
                                ),
                                summary=getattr(entry, "summary", None),
                                language=context.language,
                                content_hash=client.content_sha256(
                                    f"{link}|{getattr(entry, 'title', '')}".encode()
                                ),
                                metadata={
                                    "feed_url": feed_url,
                                    "date_unknown": published_at is None,
                                },
                            )
                        )
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{feed_url} -> {exc}")
        finally:
            if owns_client:
                client.close()

        meta["skipped_stale"] = skipped_stale

        # Deduplicate by URL while preserving order
        seen: set[str] = set()
        unique: list[DiscoveredItem] = []
        for item in items:
            if item.source_url in seen:
                continue
            seen.add(item.source_url)
            unique.append(item)

        return ConnectorResult(
            connector_type=self.connector_type,
            items=unique,
            errors=errors,
            meta=meta,
        )

    @staticmethod
    def _default_feed_candidates(base_url: str) -> list[str]:
        paths = [
            "/rss",
            "/rss.xml",
            "/feed",
            "/feed/",
            "/feeds",
            "/atom.xml",
            "/index.xml",
            "/rss/rss.xml",
            "/ar/rss",
            "/en/rss",
        ]
        return [urljoin(base_url.rstrip("/") + "/", path.lstrip("/")) for path in paths]
