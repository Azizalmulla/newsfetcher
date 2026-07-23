"""Audited production enablement for live source ingestion.

Assessment/closure writers must never call this. Ops enables sources explicitly.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import ConnectorMethod, LegalGate
from app.models.sources import Publisher, SourceChannel
from app.services.audit import write_audit

SKIP_CHANNELS = frozenset()
DEFAULT_LOOKBACK_DAYS = 5
DEFAULT_MAX_URLS = 100

# Canonical per-source discovery configs for production ingest.
SOURCE_INGEST_OVERRIDES: dict[tuple[str, str], dict[str, Any]] = {
    ("alanba", "epaper_ar"): {
        "connector_type": "epaper",
        "base_url": "https://www.alanba.com.kw",
        "config": {
            "listing_urls": ["https://www.alanba.com.kw/newspaper/"],
            "pdf_host": "https://pdf.alanba.com.kw",
            "pdf_url_template": "{host}/pdf/{yyyy}/{mm}/{dd-mm-yyyy}/{dd-mm-yyyy}.pdf",
            "download_enabled": True,
            "requires_license": False,
            "include_supplements": False,
            "max_urls": 14,
        },
    },
    ("alanba", "web_ar"): {
        "connector_type": "rss",
        "base_url": "https://www.alanba.com.kw",
        "config": {
            "feed_urls": [
                "https://www.alanba.com.kw/rss/kuwait-news",
                "https://www.alanba.com.kw/rss/economy-news",
                "https://www.alanba.com.kw/rss/sport-news",
                "https://www.alanba.com.kw/rss/art-news",
                "https://www.alanba.com.kw/rss/arabic-international-news",
                "https://www.alanba.com.kw/rss/kuwait-community",
            ],
            "max_urls": 250,
        },
    },
    ("alqabas", "web_ar"): {
        "connector_type": "html",
        "base_url": "https://www.alqabas.com",
        "config": {
            "listing_urls": ["https://www.alqabas.com/"],
            "parse_next_data": True,
            "next_data_url_template": "{base}/article/{id}/{slug}",
            "path_regex": r"^/article/\d+",
            "browser_body_fallback": True,
            "max_urls": 120,
        },
    },
    ("alrai", "web_ar"): {
        "connector_type": "html",
        "base_url": "https://www.alraimedia.com",
        "config": {
            "listing_urls": ["https://www.alraimedia.com/"],
            "path_regex": r"^/article/\d+",
            "max_urls": 100,
        },
    },
    ("alwasat", "web_ar"): {
        "connector_type": "html",
        "base_url": "https://www.alwasat.com.kw",
        "config": {
            "listing_urls": ["https://www.alwasat.com.kw/"],
            "path_regex": r"ArticleDetail\.aspx\?id=\d+",
            "max_urls": 100,
        },
    },
    ("arabtimes", "web_en"): {
        "connector_type": "html",
        "base_url": "https://www.arabtimesonline.com",
        "config": {
            "listing_urls": [
                "https://www.arabtimesonline.com/",
                "https://www.arabtimesonline.com/news/category/kuwait/",
            ],
            "path_regex": r"^/news/[^/]+/?$",
            "exclude_path_regex": r"^/news/category/",
            "max_urls": 80,
        },
    },
    ("kuwaittimes", "web_en"): {
        "connector_type": "html",
        "base_url": "https://kuwaittimes.com",
        "config": {
            "listing_urls": ["https://kuwaittimes.com/"],
            "path_regex": r"^/article/\d+",
            "max_urls": 100,
        },
    },
    ("aljarida", "web_ar"): {
        "connector_type": "html",
        "base_url": "https://www.aljarida.com",
        "config": {
            "listing_urls": ["https://www.aljarida.com/"],
            "path_regex": r"^/article/\d+",
            "max_urls": 80,
        },
    },
    ("alseyassah", "web_ar"): {
        "connector_type": "html",
        "base_url": "https://alseyassah.com",
        "config": {
            "listing_urls": [
                "https://alseyassah.com/",
                "https://alseyassah.com/%D8%A7%D9%84%D9%85%D8%AD%D9%84%D9%8A%D8%A9/",
                "https://alseyassah.com/%D8%A7%D9%84%D8%A3%D9%88%D9%84%D9%89/",
                "https://alseyassah.com/%D8%A7%D9%84%D8%AF%D9%88%D9%84%D9%8A%D8%A9/",
                "https://alseyassah.com/%D8%A7%D9%84%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF%D9%8A%D8%A9/",
            ],
            "allowed_hosts": ["alseyassah.com", "al-seyassah.com"],
            "path_regex": r"^/article/\d+",
            "max_urls": 100,
        },
    },
    ("alwatan", "web_ar"): {
        "connector_type": "browser",
        "base_url": "https://alwatan.kuwait.tt",
        "config": {
            "listing_urls": ["https://alwatan.kuwait.tt/"],
            "browser_enabled": True,
            "browser_wait_ms": 4000,
            "path_regex": r"articledetails\.aspx\?id=\d+",
            "max_urls": 80,
        },
    },
    ("kuna", "web_ar"): {
        "connector_type": "html",
        "base_url": "https://www.kuna.net.kw",
        "config": {
            "listing_urls": [
                "https://www.kuna.net.kw/",
                "https://www.kuna.net.kw/ArticleList.aspx",
            ],
            "path_regex": r"ArticleDetails\.aspx\?id=\d+",
            "max_urls": 80,
            "transport_fallback": "urllib",
        },
    },
    ("kuna", "web_en"): {
        "connector_type": "html",
        "base_url": "https://www.kuna.net.kw",
        "config": {
            "listing_urls": [
                "https://www.kuna.net.kw/",
                "https://www.kuna.net.kw/ArticleList.aspx",
            ],
            "path_regex": r"ArticleDetails\.aspx\?id=\d+",
            "max_urls": 80,
            "transport_fallback": "urllib",
        },
    },
}


def enable_web_sources(
    db: Session,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    actor_id: str | None = None,
    include_temporarily_broken: bool = True,
) -> dict[str, Any]:
    """Approve legal_gate + enable connectors for web channels (explicit ops action)."""
    publishers = db.scalars(
        select(Publisher)
        .options(
            selectinload(Publisher.channels).selectinload(SourceChannel.assessment),
            selectinload(Publisher.channels).selectinload(SourceChannel.connector_config),
        )
        .order_by(Publisher.code)
    ).all()

    enabled: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for publisher in publishers:
        for channel in publisher.channels:
            key = (publisher.code, channel.code)
            assessment = channel.assessment
            connector = channel.connector_config
            if connector is None or assessment is None:
                skipped.append(
                    {
                        "publisher": publisher.code,
                        "channel": channel.code,
                        "reason": "missing_assessment_or_connector",
                    }
                )
                continue
            if key in SKIP_CHANNELS:
                skipped.append(
                    {
                        "publisher": publisher.code,
                        "channel": channel.code,
                        "reason": "explicitly_skipped",
                    }
                )
                continue
            disposition = assessment.phase8_disposition or "active"
            # Public Al-Anba e-paper is enableable via override even if older
            # closure rows still say awaiting_licensing.
            override = SOURCE_INGEST_OVERRIDES.get(key)
            if disposition == "awaiting_licensing" and not (
                override and override.get("connector_type") == "epaper"
            ):
                skipped.append(
                    {
                        "publisher": publisher.code,
                        "channel": channel.code,
                        "reason": "awaiting_licensing",
                    }
                )
                continue
            if disposition == "blocked":
                skipped.append(
                    {
                        "publisher": publisher.code,
                        "channel": channel.code,
                        "reason": "blocked",
                    }
                )
                continue
            if disposition == "temporarily_broken" and not include_temporarily_broken:
                skipped.append(
                    {
                        "publisher": publisher.code,
                        "channel": channel.code,
                        "reason": "temporarily_broken_excluded",
                    }
                )
                continue

            if override:
                connector.connector_type = ConnectorMethod(override["connector_type"])
                if override.get("base_url"):
                    channel.base_url = str(override["base_url"])
                config = dict(override.get("config") or {})
            else:
                connector_type = str(
                    getattr(connector.connector_type, "value", connector.connector_type)
                )
                if connector_type in {"pending", "blocked"}:
                    skipped.append(
                        {
                            "publisher": publisher.code,
                            "channel": channel.code,
                            "reason": f"connector_not_scrapeable:{connector_type}",
                        }
                    )
                    continue
                config = dict(connector.config or {})

            assessment.legal_gate = LegalGate.approved
            if override and override.get("connector_type") == "epaper":
                assessment.phase8_disposition = "active"
                assessment.epaper_available = "public"
                assessment.copyright_licensing_risk = "low"
            connector.enabled = True
            config["lookback_days"] = int(lookback_days)
            config["max_urls"] = int(config.get("max_urls") or DEFAULT_MAX_URLS)
            config["ingestion_enabled"] = True
            config["requires_legal_gate"] = True
            if connector.connector_type == ConnectorMethod.epaper or (
                override and override.get("connector_type") == "epaper"
            ):
                config["download_enabled"] = True
                config.setdefault("requires_license", False)
            connector.config = config
            connector_type = str(
                getattr(connector.connector_type, "value", connector.connector_type)
            )
            if connector_type in {"html", "browser", "epaper"}:
                connector.politeness_delay_ms = max(connector.politeness_delay_ms, 1000)
            else:
                connector.politeness_delay_ms = max(connector.politeness_delay_ms, 700)
            channel.is_active = True
            # Promote temporarily_broken to active once we have a working connector path.
            if disposition == "temporarily_broken" and override:
                assessment.phase8_disposition = "active"
            enabled.append(
                {
                    "publisher": publisher.code,
                    "channel": channel.code,
                    "disposition": assessment.phase8_disposition,
                    "connector_type": connector_type,
                    "lookback_days": lookback_days,
                    "override_applied": override is not None,
                }
            )

    write_audit(
        db,
        tenant_id=None,
        actor_id=actor_id,
        action="sources.web_sources_enabled",
        resource_type="ingestion",
        resource_id="web_lookback",
        details={
            "enabled_count": len(enabled),
            "skipped": skipped,
            "lookback_days": lookback_days,
            "include_temporarily_broken": include_temporarily_broken,
        },
    )
    db.commit()
    return {
        "enabled_count": len(enabled),
        "enabled": enabled,
        "skipped": skipped,
        "lookback_days": lookback_days,
        "note": "Explicit ops approval. Assessment/closure paths still never auto-approve.",
    }


# Back-compat aliases used by older demo script imports.
DEMO_SOURCE_OVERRIDES = SOURCE_INGEST_OVERRIDES
enable_demo_web_sources = enable_web_sources
