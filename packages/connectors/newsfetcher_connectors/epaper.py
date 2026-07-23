from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from newsfetcher_connectors.base import SourceConnector
from newsfetcher_connectors.politeness import PoliteHttpClient
from newsfetcher_connectors.types import (
    ConnectorContext,
    ConnectorResult,
    ConnectorType,
    DiscoveredItem,
)

_PDF_HOST = "https://pdf.alanba.com.kw"
_FULL_EDITION_RE = re.compile(
    r"https?://pdf\.alanba\.com\.kw/pdf/(\d{4})/(\d{2})/(\d{2}-\d{2}-\d{4})/\3\.pdf",
    re.I,
)
_DATE_SLUG_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{4})$")


def _parse_edition_slug(slug: str) -> date | None:
    match = _DATE_SLUG_RE.match(slug.strip())
    if not match:
        return None
    try:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    except ValueError:
        return None


def alanba_edition_pdf_url(edition_day: date) -> str:
    slug = edition_day.strftime("%d-%m-%Y")
    return f"{_PDF_HOST}/pdf/{edition_day:%Y}/{edition_day:%m}/{slug}/{slug}.pdf"


def _head_ok(url: str, *, user_agent: str, timeout: float = 15.0) -> bool:
    headers = {"User-Agent": user_agent}
    for method, extra in (("HEAD", {}), ("GET", {"Range": "bytes=0-1023"})):
        request = Request(url, method=method, headers={**headers, **extra})
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310
                status = getattr(response, "status", 200)
                content_type = (response.headers.get("Content-Type") or "").lower()
                if status >= 400:
                    return False
                if "html" in content_type and "pdf" not in content_type:
                    return False
                return True
        except HTTPError as exc:
            if exc.code in {405, 501} and method == "HEAD":
                continue
            return False
        except (URLError, TimeoutError, ValueError):
            if method == "HEAD":
                continue
            return False
    return False


def _download_enabled(config: dict[str, Any]) -> bool:
    if config.get("download_enabled") is True:
        return True
    if config.get("ingestion_enabled") is True and config.get("requires_license") is False:
        return True
    return False


class EpaperConnector(SourceConnector):
    """Public/licensed e-paper edition discovery (Al-Anba PDF host pattern)."""

    connector_type = ConnectorType.epaper

    def __init__(self, client: PoliteHttpClient | None = None) -> None:
        self._client = client

    def discover(self, context: ConnectorContext) -> ConnectorResult:
        config = dict(context.config or {})
        download_enabled = _download_enabled(config)
        requires_license = bool(config.get("requires_license", True))

        if not download_enabled:
            return ConnectorResult(
                connector_type=self.connector_type,
                items=[],
                errors=[
                    "epaper discovery disabled until download_enabled=true "
                    "(ops enablement / public-edition confirmation)"
                ],
                meta={
                    "implemented": True,
                    "download_enabled": False,
                    "requires_license": requires_license,
                    "publisher_code": context.publisher_code,
                    "channel_code": context.channel_code,
                },
            )

        lookback_days = int(config.get("lookback_days") or 5)
        listing_urls = list(
            config.get("listing_urls")
            or [str(urljoin(str(context.base_url).rstrip("/") + "/", "newspaper/"))]
        )
        pdf_url_template = str(
            config.get("pdf_url_template")
            or "{host}/pdf/{yyyy}/{mm}/{dd-mm-yyyy}/{dd-mm-yyyy}.pdf"
        )
        include_supplements = bool(config.get("include_supplements", False))
        user_agent = context.user_agent

        items: list[DiscoveredItem] = []
        errors: list[str] = []
        seen: set[str] = set()
        probed = 0
        found = 0

        # 1) Deterministic lookback probes against known PDF URL pattern.
        today = datetime.now(UTC).date()
        for offset in range(lookback_days + 1):
            edition_day = today - timedelta(days=offset)
            slug = edition_day.strftime("%d-%m-%Y")
            url = pdf_url_template.format(
                host=_PDF_HOST,
                yyyy=edition_day.strftime("%Y"),
                mm=edition_day.strftime("%m"),
                **{"dd-mm-yyyy": slug},
            )
            probed += 1
            if not _head_ok(url, user_agent=user_agent):
                continue
            found += 1
            if url in seen:
                continue
            seen.add(url)
            items.append(
                DiscoveredItem(
                    source_url=url,
                    canonical_url=url,
                    title=f"Al-Anba e-paper {edition_day.isoformat()}",
                    published_at=datetime(
                        edition_day.year,
                        edition_day.month,
                        edition_day.day,
                        tzinfo=UTC,
                    ).isoformat(),
                    language=context.language,
                    content_hash=hashlib.sha256(url.encode()).hexdigest(),
                    metadata={
                        "kind": "epaper_edition",
                        "edition_date": edition_day.isoformat(),
                        "pdf_url": url,
                        "discovery": "url_template",
                    },
                )
            )

        # 2) Scrape newspaper listing for additional full-edition / supplement PDFs.
        client = self._client or PoliteHttpClient(
            user_agent=user_agent,
            politeness_delay_ms=context.politeness_delay_ms,
            max_requests_per_minute=context.max_requests_per_minute,
            transport_fallback="urllib",
            timeout_seconds=25.0,
        )
        owned_client = self._client is None
        try:
            for listing_url in listing_urls:
                try:
                    response = client.get(listing_url)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{listing_url} -> {exc}")
                    continue
                if response.status_code >= 400:
                    errors.append(f"{listing_url} -> HTTP {response.status_code}")
                    continue
                html = response.text
                for match in re.finditer(
                    r"https?://pdf\.alanba\.com\.kw/pdf/[^\s\"'<>]+\.pdf", html, flags=re.I
                ):
                    url = match.group(0)
                    is_full = bool(_FULL_EDITION_RE.match(url))
                    is_supplement = "/mulhak/" in url.lower()
                    if not is_full and not (include_supplements and is_supplement):
                        # Skip single-page PDFs like /12.pdf unless configured later.
                        if re.search(r"/\d+\.pdf$", url) and not is_full:
                            continue
                        if not is_supplement:
                            continue
                    if url in seen:
                        continue
                    edition_day = None
                    full = _FULL_EDITION_RE.match(url)
                    if full:
                        edition_day = _parse_edition_slug(full.group(3))
                    else:
                        slug_match = re.search(r"/(\d{2}-\d{2}-\d{4})/", url)
                        if slug_match:
                            edition_day = _parse_edition_slug(slug_match.group(1))
                    if edition_day is None:
                        continue
                    cutoff = today - timedelta(days=lookback_days)
                    if edition_day < cutoff:
                        continue
                    seen.add(url)
                    found += 1
                    items.append(
                        DiscoveredItem(
                            source_url=url,
                            canonical_url=url,
                            title=(
                                f"Al-Anba supplement {edition_day.isoformat()}"
                                if is_supplement
                                else f"Al-Anba e-paper {edition_day.isoformat()}"
                            ),
                            published_at=datetime(
                                edition_day.year,
                                edition_day.month,
                                edition_day.day,
                                tzinfo=UTC,
                            ).isoformat(),
                            language=context.language,
                            content_hash=hashlib.sha256(url.encode()).hexdigest(),
                            metadata={
                                "kind": "epaper_edition",
                                "edition_date": edition_day.isoformat(),
                                "pdf_url": url,
                                "discovery": "listing_html",
                                "supplement": is_supplement,
                            },
                        )
                    )
        finally:
            if owned_client:
                client.close()

        return ConnectorResult(
            connector_type=self.connector_type,
            items=items,
            errors=errors,
            meta={
                "implemented": True,
                "download_enabled": True,
                "requires_license": requires_license,
                "publisher_code": context.publisher_code,
                "channel_code": context.channel_code,
                "probed_template_urls": probed,
                "editions_found": found,
                "lookback_days": lookback_days,
            },
        )

    def health_probe(self, context: ConnectorContext) -> dict[str, object]:
        listing = str(
            (context.config or {}).get("listing_urls")
            or [urljoin(str(context.base_url).rstrip("/") + "/", "newspaper/")]
        )
        return {
            "ok": True,
            "status_code": None,
            "connector_type": self.connector_type.value,
            "url": listing if isinstance(listing, str) else str(context.base_url),
            "note": "epaper probe is non-fetching by default; discovery uses HEAD/GET when enabled",
        }
