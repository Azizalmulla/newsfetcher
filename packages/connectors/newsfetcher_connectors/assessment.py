"""Passive source assessment probes (robots, feeds, sitemap). No article body scraping."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser
from urllib.request import Request, urlopen

import feedparser
import httpx

from newsfetcher_connectors.politeness import PoliteHttpClient


@dataclass
class AssessmentProbeResult:
    homepage_status: int | None = None
    robots_txt_url: str | None = None
    robots_allows_fetch: str = "unknown"
    robots_notes: str = ""
    rss_available: str = "unknown"
    rss_feeds: list[str] = field(default_factory=list)
    sitemap_available: str = "unknown"
    sitemap_urls: list[str] = field(default_factory=list)
    auth_paywall_status: str = "unknown"
    recommended_connector: str = "pending"
    status: str = "pending_assessment"
    errors: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


COMMON_RSS_PATHS = [
    "/rss",
    "/rss.xml",
    "/feed",
    "/feed/",
    "/atom.xml",
    "/index.xml",
    "/rss/rss.xml",
]

COMMON_SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
]


def _fetch_bytes(
    http: PoliteHttpClient, url: str, *, user_agent: str
) -> tuple[int, bytes, dict[str, str]]:
    """Fetch with polite client; fall back to urllib for broken HTTP implementations."""
    try:
        response = http.get(url, use_cache=False)
        return response.status_code, response.content, dict(response.headers)
    except Exception as primary:  # noqa: BLE001
        try:
            request = Request(url, headers={"User-Agent": user_agent})
            with urlopen(request, timeout=20) as resp:  # noqa: S310 - assessment of public URLs
                return int(resp.status), resp.read(), dict(resp.headers.items())
        except Exception as secondary:  # noqa: BLE001
            raise RuntimeError(f"{primary}; urllib fallback: {secondary}") from secondary


def _looks_like_feed(content: bytes, content_type: str) -> bool:
    ctype = content_type.lower()
    if any(token in ctype for token in ("rss", "atom", "xml")) and b"<html" not in content[:800].lower():
        parsed = feedparser.parse(content)
        return bool(parsed.entries)
    head = content[:2000].lower()
    if b"<html" in head:
        return False
    if b"<rss" in head or b"<feed" in head or b"<rdf:rdf" in head:
        parsed = feedparser.parse(content)
        return bool(parsed.entries)
    return False


def _looks_like_sitemap(content: bytes) -> bool:
    head = content[:3000].lower()
    if b"<html" in head:
        return False
    return b"<urlset" in head or b"<sitemapindex" in head


def assess_source(
    base_url: str,
    *,
    user_agent: str = "NewsFetcherBot/0.1 (+assessment; contact=ops@newsfetcher.local)",
    client: PoliteHttpClient | None = None,
) -> AssessmentProbeResult:
    """Run a polite, read-only assessment against public discovery endpoints."""
    owns = client is None
    http = client or PoliteHttpClient(
        user_agent=user_agent,
        politeness_delay_ms=800,
        max_requests_per_minute=12,
    )
    result = AssessmentProbeResult()
    try:
        try:
            status, body, headers = _fetch_bytes(http, base_url, user_agent=user_agent)
            result.homepage_status = status
            if status in {401, 402, 403}:
                result.auth_paywall_status = "hard"
            elif status < 400:
                body_lower = body.decode("utf-8", errors="ignore").lower()
                if "paywall" in body_lower or (
                    "subscribe" in body_lower and "login" in body_lower
                ):
                    result.auth_paywall_status = "soft"
                else:
                    result.auth_paywall_status = "none"
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"homepage: {exc}")
            result.status = "temporarily_broken"
            result.recommended_connector = "pending"
            result.raw = {"errors": result.errors}
            return result

        robots_url = urljoin(base_url.rstrip("/") + "/", "robots.txt")
        result.robots_txt_url = robots_url
        try:
            status, body, _headers = _fetch_bytes(http, robots_url, user_agent=user_agent)
            if status < 400:
                text = body.decode("utf-8", errors="ignore")
                rp = RobotFileParser()
                rp.parse(text.splitlines())
                allowed = rp.can_fetch(user_agent, base_url)
                result.robots_allows_fetch = "yes" if allowed else "no"
                result.robots_notes = f"robots.txt HTTP {status}"
                for line in text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        sitemap = line.split(":", 1)[1].strip()
                        if sitemap and sitemap not in result.sitemap_urls:
                            result.sitemap_urls.append(sitemap)
            else:
                result.robots_allows_fetch = "unknown"
                result.robots_notes = f"robots.txt HTTP {status}"
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"robots: {exc}")

        for path in COMMON_RSS_PATHS:
            feed_url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
            try:
                status, body, headers = _fetch_bytes(http, feed_url, user_agent=user_agent)
                ctype = headers.get("content-type", headers.get("Content-Type", ""))
                if status < 400 and _looks_like_feed(body, ctype):
                    result.rss_feeds.append(feed_url)
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"rss {feed_url}: {exc}")
        result.rss_available = "yes" if result.rss_feeds else "no"

        for path in COMMON_SITEMAP_PATHS:
            sm_url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
            if sm_url in result.sitemap_urls:
                continue
            try:
                status, body, _headers = _fetch_bytes(http, sm_url, user_agent=user_agent)
                if status < 400 and _looks_like_sitemap(body):
                    result.sitemap_urls.append(sm_url)
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"sitemap {sm_url}: {exc}")

        # Validate robots-declared sitemaps
        validated_sitemaps: list[str] = []
        for sm_url in result.sitemap_urls:
            try:
                status, body, _headers = _fetch_bytes(http, sm_url, user_agent=user_agent)
                if status < 400 and _looks_like_sitemap(body):
                    validated_sitemaps.append(sm_url)
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"sitemap-validate {sm_url}: {exc}")
        result.sitemap_urls = validated_sitemaps
        result.sitemap_available = "yes" if result.sitemap_urls else "no"

        result.recommended_connector, result.status = _recommend(result)
        result.raw = {
            "homepage_status": result.homepage_status,
            "rss_feeds": result.rss_feeds,
            "sitemap_urls": result.sitemap_urls,
            "robots_allows_fetch": result.robots_allows_fetch,
            "auth_paywall_status": result.auth_paywall_status,
        }
        return result
    except httpx.HTTPError as exc:
        result.errors.append(str(exc))
        result.status = "temporarily_broken"
        result.recommended_connector = "pending"
        return result
    finally:
        if owns:
            http.close()


def _recommend(result: AssessmentProbeResult) -> tuple[str, str]:
    if result.homepage_status and result.homepage_status >= 500:
        return "pending", "temporarily_broken"
    if result.auth_paywall_status == "hard":
        return "blocked", "blocked_by_paywall"
    if result.robots_allows_fetch == "no":
        return "blocked", "disabled"
    if result.rss_available == "yes":
        return "rss", "approved_for_rss"
    if result.sitemap_available == "yes":
        return "sitemap", "approved_for_html_fetch"
    if result.homepage_status and result.homepage_status < 400:
        return "html", "approved_for_html_fetch"
    return "pending", "pending_assessment"
