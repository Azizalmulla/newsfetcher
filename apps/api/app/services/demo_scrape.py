"""Back-compat shim. Prefer source_enablement + ingestion_pipeline."""

from app.services.ingestion_pipeline import (
    discover_all_enabled,
    run_demo_five_day_scrape,
    run_lookback_ingest,
)
from app.services.source_enablement import (
    DEMO_SOURCE_OVERRIDES,
    SOURCE_INGEST_OVERRIDES,
    enable_demo_web_sources,
    enable_web_sources,
)

__all__ = [
    "DEMO_SOURCE_OVERRIDES",
    "SOURCE_INGEST_OVERRIDES",
    "discover_all_enabled",
    "enable_demo_web_sources",
    "enable_web_sources",
    "run_demo_five_day_scrape",
    "run_lookback_ingest",
]
