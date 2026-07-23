from __future__ import annotations

from newsfetcher_connectors.base import SourceConnector
from newsfetcher_connectors.browser import BrowserConnector
from newsfetcher_connectors.epaper import EpaperConnector
from newsfetcher_connectors.html import HtmlConnector
from newsfetcher_connectors.licensed_api import LicensedApiConnector
from newsfetcher_connectors.rss import RssConnector
from newsfetcher_connectors.sitemap import SitemapConnector
from newsfetcher_connectors.types import ConnectorType

_REGISTRY: dict[ConnectorType, type[SourceConnector]] = {
    ConnectorType.rss: RssConnector,
    ConnectorType.sitemap: SitemapConnector,
    ConnectorType.html: HtmlConnector,
    ConnectorType.browser: BrowserConnector,
    ConnectorType.licensed_api: LicensedApiConnector,
    ConnectorType.epaper: EpaperConnector,
}


def get_connector(connector_type: ConnectorType | str) -> SourceConnector:
    key = ConnectorType(connector_type)
    try:
        return _REGISTRY[key]()
    except KeyError as exc:
        raise ValueError(f"No connector implementation for {key}") from exc


def list_connector_types() -> list[str]:
    return [item.value for item in _REGISTRY]
