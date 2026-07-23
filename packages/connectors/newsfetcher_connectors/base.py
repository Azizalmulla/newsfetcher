from __future__ import annotations

from abc import ABC, abstractmethod

from newsfetcher_connectors.politeness import PoliteHttpClient
from newsfetcher_connectors.types import (
    ConnectorContext,
    ConnectorResult,
    ConnectorType,
    DiscoveredItem,
)

__all__ = [
    "ConnectorContext",
    "ConnectorResult",
    "ConnectorType",
    "DiscoveredItem",
    "SourceConnector",
]


class SourceConnector(ABC):
    connector_type: ConnectorType

    def __init__(self, client: PoliteHttpClient | None = None) -> None:
        self._client = client

    def _http(self, context: ConnectorContext) -> PoliteHttpClient:
        if self._client is not None:
            return self._client
        fallback = context.config.get("transport_fallback")
        return PoliteHttpClient(
            user_agent=context.user_agent,
            politeness_delay_ms=context.politeness_delay_ms,
            max_requests_per_minute=context.max_requests_per_minute,
            transport_fallback=str(fallback) if fallback else None,
        )

    @abstractmethod
    def discover(self, context: ConnectorContext) -> ConnectorResult:
        """Discover article candidates. Must not bypass paywalls or auth walls."""

    def health_probe(self, context: ConnectorContext) -> dict[str, object]:
        """Lightweight probe used by source.health jobs."""
        client = self._http(context)
        owns_client = self._client is None
        try:
            response = client.get(str(context.base_url), use_cache=False)
            return {
                "ok": response.status_code < 400,
                "status_code": response.status_code,
                "connector_type": self.connector_type.value,
                "url": str(context.base_url),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "error": str(exc),
                "connector_type": self.connector_type.value,
                "url": str(context.base_url),
            }
        finally:
            if owns_client:
                client.close()
