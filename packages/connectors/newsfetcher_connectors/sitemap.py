from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin

from newsfetcher_connectors.base import SourceConnector
from newsfetcher_connectors.types import (
    ConnectorContext,
    ConnectorResult,
    ConnectorType,
    DiscoveredItem,
)

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _parse_lastmod(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except ValueError:
            continue
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except ValueError:
            continue
    return None


class SitemapConnector(SourceConnector):
    connector_type = ConnectorType.sitemap

    def discover(self, context: ConnectorContext) -> ConnectorResult:
        sitemap_urls = context.config.get("sitemap_urls") or [
            urljoin(str(context.base_url).rstrip("/") + "/", "sitemap.xml"),
            urljoin(str(context.base_url).rstrip("/") + "/", "sitemap_index.xml"),
        ]
        max_urls = int(context.config.get("max_urls", 200))
        lookback_days = context.config.get("lookback_days")
        cutoff = None
        if lookback_days is not None:
            cutoff = datetime.now(UTC) - timedelta(days=int(lookback_days))

        client = self._http(context)
        owns_client = self._client is None
        items: list[DiscoveredItem] = []
        errors: list[str] = []
        meta: dict[str, object] = {
            "sitemaps_tried": [],
            "sitemaps_ok": [],
            "lookback_days": lookback_days,
            "skipped_stale": 0,
        }

        try:
            for sitemap_url in sitemap_urls:
                if len(items) >= max_urls:
                    break
                meta["sitemaps_tried"].append(sitemap_url)  # type: ignore[index]
                try:
                    response = client.get(sitemap_url)
                    if response.status_code >= 400:
                        errors.append(f"{sitemap_url} -> HTTP {response.status_code}")
                        continue
                    root = ET.fromstring(response.content)
                    meta["sitemaps_ok"].append(sitemap_url)  # type: ignore[index]
                    tag = root.tag.lower()
                    if tag.endswith("sitemapindex"):
                        nested = [
                            loc.text.strip()
                            for loc in root.findall("sm:sitemap/sm:loc", SITEMAP_NS)
                            if loc.text
                        ]
                        if not nested:
                            nested = [
                                el.text.strip()
                                for el in root.findall(".//{*}loc")
                                if el.text and el.text.strip().endswith(".xml")
                            ]
                        for nested_url in nested[:20]:
                            nested_result, skipped = self._parse_urlset(
                                client.get(nested_url).content,
                                language=context.language,
                                max_urls=max_urls - len(items),
                                content_hash_fn=client.content_sha256,
                                sitemap_url=nested_url,
                                cutoff=cutoff,
                            )
                            meta["skipped_stale"] = int(meta["skipped_stale"]) + skipped
                            items.extend(nested_result)
                            if len(items) >= max_urls:
                                break
                    else:
                        parsed, skipped = self._parse_urlset(
                            response.content,
                            language=context.language,
                            max_urls=max_urls - len(items),
                            content_hash_fn=client.content_sha256,
                            sitemap_url=sitemap_url,
                            cutoff=cutoff,
                        )
                        meta["skipped_stale"] = int(meta["skipped_stale"]) + skipped
                        items.extend(parsed)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{sitemap_url} -> {exc}")
        finally:
            if owns_client:
                client.close()

        return ConnectorResult(
            connector_type=self.connector_type,
            items=items[:max_urls],
            errors=errors,
            meta=meta,
        )

    @staticmethod
    def _parse_urlset(
        content: bytes,
        *,
        language: str,
        max_urls: int,
        content_hash_fn: Callable[[bytes], str],
        sitemap_url: str,
        cutoff: datetime | None,
    ) -> tuple[list[DiscoveredItem], int]:
        root = ET.fromstring(content)
        url_nodes = list(root.findall("sm:url", SITEMAP_NS))
        if not url_nodes:
            url_nodes = list(root.findall(".//{*}url"))

        items: list[DiscoveredItem] = []
        skipped = 0
        if url_nodes:
            for node in url_nodes:
                loc_el = node.find("sm:loc", SITEMAP_NS)
                if loc_el is None:
                    loc_el = node.find("{*}loc")
                if loc_el is None or not loc_el.text:
                    continue
                loc = loc_el.text.strip()
                if loc.endswith(".xml"):
                    continue
                lastmod_el = node.find("sm:lastmod", SITEMAP_NS)
                if lastmod_el is None:
                    lastmod_el = node.find("{*}lastmod")
                lastmod = _parse_lastmod(lastmod_el.text if lastmod_el is not None else None)
                if cutoff is not None and lastmod is not None and lastmod < cutoff:
                    skipped += 1
                    continue
                items.append(
                    DiscoveredItem(
                        source_url=loc,
                        canonical_url=loc,
                        published_at=lastmod.isoformat() if lastmod else None,
                        language=language,  # type: ignore[arg-type]
                        content_hash=content_hash_fn(loc.encode()),
                        metadata={
                            "sitemap_url": sitemap_url,
                            "lastmod": lastmod.isoformat() if lastmod else None,
                            "date_unknown": lastmod is None,
                        },
                    )
                )
                if len(items) >= max_urls:
                    break
            return items, skipped

        locs = [el.text.strip() for el in root.findall(".//{*}loc") if el.text]
        for loc in locs:
            if loc.endswith(".xml"):
                continue
            items.append(
                DiscoveredItem(
                    source_url=loc,
                    canonical_url=loc,
                    language=language,  # type: ignore[arg-type]
                    content_hash=content_hash_fn(loc.encode()),
                    metadata={"sitemap_url": sitemap_url, "date_unknown": True},
                )
            )
            if len(items) >= max_urls:
                break
        return items, skipped
