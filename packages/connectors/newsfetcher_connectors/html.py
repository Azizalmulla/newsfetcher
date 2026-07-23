from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote, unquote, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from newsfetcher_connectors.base import SourceConnector
from newsfetcher_connectors.types import (
    ConnectorContext,
    ConnectorResult,
    ConnectorType,
    DiscoveredItem,
)


class HtmlConnector(SourceConnector):
    """Static HTML listing discovery. Does not render JavaScript.

    Supports optional Next.js `__NEXT_DATA__` extraction for SPA homepages
    (e.g. Al-Qabas) via config `parse_next_data=true`.
    """

    connector_type = ConnectorType.html

    def discover(self, context: ConnectorContext) -> ConnectorResult:
        listing_urls = context.config.get("listing_urls") or [str(context.base_url)]
        link_selector = context.config.get("link_selector", "a[href]")
        allowed_path_prefixes = context.config.get("allowed_path_prefixes") or []
        path_regex = context.config.get("path_regex")
        exclude_path_regex = context.config.get("exclude_path_regex")
        allowed_hosts = {
            h.lower().removeprefix("www.")
            for h in (context.config.get("allowed_hosts") or [])
            if h
        }
        max_urls = int(context.config.get("max_urls", 100))
        parse_next_data = bool(context.config.get("parse_next_data"))
        next_data_url_template = context.config.get(
            "next_data_url_template", "{base}/article/{id}/{slug}"
        )
        path_re = re.compile(path_regex) if path_regex else None
        exclude_re = re.compile(exclude_path_regex) if exclude_path_regex else None

        client = self._http(context)
        owns_client = self._client is None
        items: list[DiscoveredItem] = []
        errors: list[str] = []
        seen: set[str] = set()
        meta: dict[str, object] = {
            "pages_tried": [],
            "pages_ok": [],
            "path_regex": path_regex,
            "parse_next_data": parse_next_data,
            "next_data_items": 0,
        }

        try:
            for listing_url in listing_urls:
                if len(items) >= max_urls:
                    break
                meta["pages_tried"].append(listing_url)  # type: ignore[index]
                try:
                    request_url = self._request_url(
                        listing_url,
                        proxy_base_url=context.config.get("proxy_base_url"),
                    )
                    response = client.get(request_url)
                    if response.status_code >= 400:
                        errors.append(f"{listing_url} -> HTTP {response.status_code}")
                        continue
                    meta["pages_ok"].append(listing_url)  # type: ignore[index]
                    base_for_template = (
                        f"{urlparse(str(response.url)).scheme}://"
                        f"{urlparse(str(response.url)).netloc}"
                    )

                    if parse_next_data:
                        next_items = self._items_from_next_data(
                            response.text,
                            base_url=base_for_template,
                            url_template=next_data_url_template,
                            language=context.language,
                            content_hash_fn=client.content_sha256,
                            listing_url=listing_url,
                            max_urls=max_urls - len(items),
                        )
                        meta["next_data_items"] = int(meta["next_data_items"]) + len(
                            next_items
                        )
                        for item in next_items:
                            if item.source_url in seen:
                                continue
                            seen.add(item.source_url)
                            items.append(item)
                            if len(items) >= max_urls:
                                break
                        if len(items) >= max_urls:
                            break

                    soup = BeautifulSoup(response.content, "lxml")
                    for anchor in soup.select(link_selector):
                        href = anchor.get("href")
                        if not href or href.startswith("#") or href.startswith("mailto:"):
                            continue
                        absolute = self._normalize_url(urljoin(listing_url, href))
                        if absolute in seen:
                            continue
                        if not self._same_site(
                            str(context.base_url), absolute, allowed_hosts=allowed_hosts
                        ):
                            continue
                        path = urlparse(absolute).path
                        query = urlparse(absolute).query
                        path_and_query = path + (("?" + query) if query else "")
                        if allowed_path_prefixes and not any(
                            path_and_query.startswith(prefix) or path.startswith(prefix)
                            for prefix in allowed_path_prefixes
                        ):
                            continue
                        if path_re and not path_re.search(path_and_query):
                            continue
                        if exclude_re and exclude_re.search(path_and_query):
                            continue
                        title = anchor.get_text(" ", strip=True) or None
                        if title and len(title) < 8:
                            title = None
                        seen.add(absolute)
                        items.append(
                            DiscoveredItem(
                                source_url=absolute,
                                canonical_url=absolute,
                                title=title,
                                language=context.language,
                                content_hash=client.content_sha256(
                                    f"{absolute}|{title or ''}".encode()
                                ),
                                metadata={"listing_url": listing_url},
                            )
                        )
                        if len(items) >= max_urls:
                            break
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{listing_url} -> {exc}")
        finally:
            if owns_client:
                client.close()

        return ConnectorResult(
            connector_type=self.connector_type,
            items=items,
            errors=errors,
            meta=meta,
        )

    @classmethod
    def _items_from_next_data(
        cls,
        html: str,
        *,
        base_url: str,
        url_template: str,
        language: str,
        content_hash_fn: Any,
        listing_url: str,
        max_urls: int,
    ) -> list[DiscoveredItem]:
        match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, flags=re.S
        )
        if not match:
            return []
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []

        articles: list[dict[str, Any]] = []
        for node in cls._walk(payload.get("props", {}).get("pageProps", {})):
            if not isinstance(node, dict):
                continue
            article_id = node.get("id") or node.get("articleId") or node.get("Id")
            slug = node.get("slug") or node.get("Slug")
            title = node.get("title") or node.get("Title")
            if article_id and slug:
                articles.append(
                    {
                        "id": str(article_id),
                        "slug": str(slug),
                        "title": str(title) if title else None,
                    }
                )

        items: list[DiscoveredItem] = []
        seen: set[str] = set()
        for article in articles:
            slug_raw = article["slug"]
            slug = unquote(slug_raw)
            url = url_template.format(
                base=base_url.rstrip("/"),
                id=article["id"],
                slug=quote(slug, safe="-"),
            )
            if url in seen:
                continue
            seen.add(url)
            items.append(
                DiscoveredItem(
                    source_url=url,
                    canonical_url=url,
                    title=article["title"],
                    language=language,  # type: ignore[arg-type]
                    content_hash=content_hash_fn(
                        f"{url}|{article['title'] or ''}".encode()
                    ),
                    metadata={
                        "listing_url": listing_url,
                        "discovery": "next_data",
                        "article_id": article["id"],
                    },
                )
            )
            if len(items) >= max_urls:
                break
        return items

    @classmethod
    def _walk(cls, obj: Any) -> Any:
        if isinstance(obj, dict):
            yield obj
            for value in obj.values():
                yield from cls._walk(value)
        elif isinstance(obj, list):
            for value in obj:
                yield from cls._walk(value)

    @staticmethod
    def _normalize_url(url: str) -> str:
        parts = urlparse(url)
        return urlunparse((parts.scheme, parts.netloc, parts.path, "", parts.query, ""))

    @staticmethod
    def _request_url(url: str, *, proxy_base_url: str | None) -> str:
        if not proxy_base_url:
            return url
        return f"{proxy_base_url.rstrip('/')}?{urlencode({'url': url})}"

    @staticmethod
    def _same_site(
        base_url: str, candidate: str, *, allowed_hosts: set[str] | None = None
    ) -> bool:
        base = urlparse(base_url)
        other = urlparse(candidate)
        if other.scheme not in {"http", "https"}:
            return False
        other_host = (other.netloc or "").lower().removeprefix("www.")
        base_host = (base.netloc or "").lower().removeprefix("www.")
        if allowed_hosts and other_host in allowed_hosts:
            return True
        return bool(base_host) and base_host == other_host
