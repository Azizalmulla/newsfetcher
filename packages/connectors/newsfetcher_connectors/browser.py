"""Playwright-backed discovery for JS cookie walls / client-rendered listings.

Only used when connector_type=browser, legal_gate=approved, and enabled=true.
Does not bypass paywalls or solve CAPTCHAs.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from newsfetcher_connectors.base import SourceConnector
from newsfetcher_connectors.types import (
    ConnectorContext,
    ConnectorResult,
    ConnectorType,
    DiscoveredItem,
)


def playwright_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


def fetch_rendered_html(
    url: str,
    *,
    user_agent: str,
    wait_ms: int = 2500,
    timeout_ms: int = 30000,
) -> tuple[int, str]:
    """Render a URL in Chromium and return final status + HTML."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(user_agent=user_agent, locale="ar-KW")
            page = context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(wait_ms)
            # Cookie-challenge pages often reload once after setCookie.
            page.wait_for_timeout(1500)
            html = page.content()
            status = response.status if response is not None else 200
            return status, html
        finally:
            browser.close()


class BrowserConnector(SourceConnector):
    connector_type = ConnectorType.browser

    def discover(self, context: ConnectorContext) -> ConnectorResult:
        # Fail closed: browser discovery only runs when explicitly enabled in config.
        if not bool(context.config.get("browser_enabled", False)):
            return ConnectorResult(
                connector_type=self.connector_type,
                items=[],
                errors=["browser_enabled not set; refusing to launch browser runtime"],
                meta={"implemented": True, "skipped": True, "requires_explicit_enable": True},
            )
        if not playwright_available():
            return ConnectorResult(
                connector_type=self.connector_type,
                items=[],
                errors=["playwright_not_installed"],
                meta={"implemented": True, "requires_browser_runtime": True},
            )

        listing_urls = context.config.get("listing_urls") or [str(context.base_url)]
        path_regex = context.config.get("path_regex")
        path_re = re.compile(path_regex) if path_regex else None
        max_urls = int(context.config.get("max_urls", 80))
        wait_ms = int(context.config.get("browser_wait_ms", 3000))

        items: list[DiscoveredItem] = []
        errors: list[str] = []
        seen: set[str] = set()
        meta: dict[str, Any] = {"pages_tried": [], "pages_ok": [], "engine": "playwright"}

        for listing_url in listing_urls:
            if len(items) >= max_urls:
                break
            meta["pages_tried"].append(listing_url)
            try:
                status, html = fetch_rendered_html(
                    listing_url,
                    user_agent=context.user_agent,
                    wait_ms=wait_ms,
                )
                if status >= 400:
                    errors.append(f"{listing_url} -> HTTP {status}")
                    continue
                meta["pages_ok"].append(listing_url)
                hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I)
                for href in hrefs:
                    if href.startswith("#") or href.startswith("mailto:"):
                        continue
                    absolute = urljoin(listing_url, href)
                    if absolute in seen:
                        continue
                    if not self._same_site(str(context.base_url), absolute):
                        continue
                    path = urlparse(absolute).path
                    if path_re and not path_re.search(path + (("?" + urlparse(absolute).query) if urlparse(absolute).query else "")):
                        continue
                    seen.add(absolute)
                    items.append(
                        DiscoveredItem(
                            source_url=absolute,
                            canonical_url=absolute,
                            language=context.language,
                            content_hash=hashlib.sha256(absolute.encode()).hexdigest(),
                            metadata={"listing_url": listing_url, "discovery": "playwright"},
                        )
                    )
                    if len(items) >= max_urls:
                        break
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{listing_url} -> {exc}")

        return ConnectorResult(
            connector_type=self.connector_type,
            items=items,
            errors=errors,
            meta=meta,
        )

    def health_probe(self, context: ConnectorContext) -> dict[str, object]:
        base = {
            "connector_type": self.connector_type.value,
            "url": str(context.base_url),
            "playwright_available": playwright_available(),
        }
        if not playwright_available():
            return {**base, "ok": False, "error": "playwright_not_installed"}
        try:
            status, html = fetch_rendered_html(
                str(context.base_url),
                user_agent=context.user_agent,
                wait_ms=int(context.config.get("browser_wait_ms", 2000)),
            )
            return {
                **base,
                "ok": status < 400 and len(html) > 2000,
                "status_code": status,
                "html_bytes": len(html),
            }
        except Exception as exc:  # noqa: BLE001
            return {**base, "ok": False, "error": str(exc)}

    @staticmethod
    def _same_site(base_url: str, candidate: str) -> bool:
        base = urlparse(base_url)
        other = urlparse(candidate)
        if other.scheme not in {"http", "https"}:
            return False
        return base.netloc.lower().removeprefix("www.") == other.netloc.lower().removeprefix(
            "www."
        )
