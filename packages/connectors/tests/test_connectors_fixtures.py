from __future__ import annotations

from pathlib import Path

import httpx

from newsfetcher_connectors.epaper import EpaperConnector
from newsfetcher_connectors.html import HtmlConnector
from newsfetcher_connectors.politeness import PoliteHttpClient
from newsfetcher_connectors.registry import list_connector_types
from newsfetcher_connectors.rss import RssConnector
from newsfetcher_connectors.sitemap import SitemapConnector
from newsfetcher_connectors.types import ConnectorContext

FIXTURES = Path(__file__).parent / "fixtures"


class FixtureTransport(httpx.BaseTransport):
    def __init__(self, mapping: dict[str, tuple[int, bytes, str]]) -> None:
        self.mapping = mapping

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        key = str(request.url)
        if key not in self.mapping:
            return httpx.Response(404, request=request, content=b"missing")
        status, body, content_type = self.mapping[key]
        return httpx.Response(
            status,
            request=request,
            content=body,
            headers={"content-type": content_type},
        )


def _context(**config):  # type: ignore[no-untyped-def]
    return ConnectorContext(
        publisher_code="example",
        channel_code="web_en",
        base_url="https://example.test",
        language="en",
        config=config,
        politeness_delay_ms=0,
        max_requests_per_minute=1000,
    )


def test_rss_connector_parses_fixture_feed() -> None:
    feed = (FIXTURES / "sample_feed.xml").read_bytes()
    transport = FixtureTransport(
        {"https://example.test/rss.xml": (200, feed, "application/rss+xml")}
    )
    client = PoliteHttpClient(
        user_agent="test",
        politeness_delay_ms=0,
        max_requests_per_minute=1000,
        transport=transport,
    )
    result = RssConnector(client=client).discover(
        _context(feed_urls=["https://example.test/rss.xml"])
    )
    assert len(result.items) == 2
    assert result.items[0].title == "First Story"
    assert result.errors == []


def test_sitemap_connector_parses_fixture() -> None:
    sitemap = (FIXTURES / "sample_sitemap.xml").read_bytes()
    transport = FixtureTransport(
        {"https://example.test/sitemap.xml": (200, sitemap, "application/xml")}
    )
    client = PoliteHttpClient(
        user_agent="test",
        politeness_delay_ms=0,
        max_requests_per_minute=1000,
        transport=transport,
    )
    result = SitemapConnector(client=client).discover(
        _context(sitemap_urls=["https://example.test/sitemap.xml"])
    )
    assert len(result.items) == 3
    assert result.items[0].source_url.endswith("/articles/a")


def test_html_connector_same_site_only() -> None:
    html = (FIXTURES / "sample_listing.html").read_bytes()
    transport = FixtureTransport(
        {"https://example.test/": (200, html, "text/html")}
    )
    client = PoliteHttpClient(
        user_agent="test",
        politeness_delay_ms=0,
        max_requests_per_minute=1000,
        transport=transport,
    )
    result = HtmlConnector(client=client).discover(
        _context(listing_urls=["https://example.test/"], allowed_path_prefixes=["/articles/"])
    )
    urls = {item.source_url for item in result.items}
    assert "https://example.test/articles/one" in urls
    assert "https://example.test/articles/two" in urls
    assert "https://other.test/out" not in urls


def test_phase8_connectors_registered() -> None:
    types = set(list_connector_types())
    assert "epaper" in types
    assert "browser" in types
    assert "licensed_api" in types
    result = EpaperConnector().discover(_context(requires_license=True))
    assert result.items == []
    assert result.meta["download_enabled"] is False


def test_epaper_discovers_when_download_enabled(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from newsfetcher_connectors import epaper as epaper_mod

    monkeypatch.setattr(epaper_mod, "_head_ok", lambda url, user_agent, timeout=15.0: "23-07-2026" in url)
    transport = FixtureTransport(
        {
            "https://www.alanba.com.kw/newspaper/": (
                200,
                b"<a href='https://pdf.alanba.com.kw/pdf/2026/07/23-07-2026/23-07-2026.pdf'>x</a>",
                "text/html",
            )
        }
    )
    client = PoliteHttpClient(
        user_agent="test",
        politeness_delay_ms=0,
        max_requests_per_minute=1000,
        transport=transport,
    )
    result = EpaperConnector(client=client).discover(
        ConnectorContext(
            publisher_code="alanba",
            channel_code="epaper_ar",
            base_url="https://www.alanba.com.kw",
            language="ar",
            config={
                "download_enabled": True,
                "requires_license": False,
                "lookback_days": 1,
                "listing_urls": ["https://www.alanba.com.kw/newspaper/"],
            },
            politeness_delay_ms=0,
            max_requests_per_minute=1000,
        )
    )
    assert result.meta["download_enabled"] is True
    assert any(i.metadata.get("kind") == "epaper_edition" for i in result.items)
    assert any("23-07-2026.pdf" in i.source_url for i in result.items)


def test_politeness_circuit_opens_after_failures() -> None:
    class AlwaysFail(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

    client = PoliteHttpClient(
        user_agent="test",
        politeness_delay_ms=0,
        max_requests_per_minute=1000,
        max_retries=1,
        failure_threshold=2,
        circuit_open_seconds=60,
        transport=AlwaysFail(),
    )
    failed = 0
    for _ in range(2):
        try:
            client.get("https://example.test/x")
        except RuntimeError:
            failed += 1
    assert failed == 2
    try:
        client.get("https://example.test/x")
        raised = False
    except RuntimeError as exc:
        raised = True
        assert "Circuit open" in str(exc)
    assert raised
