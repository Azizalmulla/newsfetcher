"""NewsFetcher connector framework (Phase 1+)."""

from newsfetcher_connectors.base import (
    ConnectorContext,
    ConnectorResult,
    DiscoveredItem,
    SourceConnector,
)
from newsfetcher_connectors.registry import get_connector, list_connector_types

__all__ = [
    "ConnectorContext",
    "ConnectorResult",
    "DiscoveredItem",
    "SourceConnector",
    "get_connector",
    "list_connector_types",
]
