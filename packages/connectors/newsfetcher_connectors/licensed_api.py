from __future__ import annotations

from newsfetcher_connectors.base import SourceConnector
from newsfetcher_connectors.types import ConnectorContext, ConnectorResult, ConnectorType


class LicensedApiConnector(SourceConnector):
    """Skeleton for licensed publisher APIs. Credentials never hardcoded."""

    connector_type = ConnectorType.licensed_api

    def discover(self, context: ConnectorContext) -> ConnectorResult:
        api_base = context.config.get("api_base_url")
        return ConnectorResult(
            connector_type=self.connector_type,
            items=[],
            errors=[
                "licensed_api connector awaits credentials + legal approval; "
                "discovery intentionally empty"
            ],
            meta={
                "implemented": False,
                "api_base_url": api_base,
                "requires_license": True,
                "publisher_code": context.publisher_code,
                "channel_code": context.channel_code,
            },
        )
