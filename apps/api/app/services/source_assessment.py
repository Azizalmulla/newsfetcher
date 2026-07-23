"""Persist polite technical assessments. Legal gate stays pending until human approval."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from newsfetcher_connectors.assessment import assess_source
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import ConnectorMethod, LegalGate, SourceAssessmentStatus
from app.models.sources import Publisher, SourceAssessment, SourceChannel, SourceConnectorConfig

DOCS_SOURCES = Path(__file__).resolve().parents[4] / "docs" / "sources" / "assessments"


def run_assessments(db: Session, *, write_docs: bool = True) -> list[dict[str, Any]]:
    publishers = db.scalars(
        select(Publisher).options(selectinload(Publisher.channels)).order_by(Publisher.code)
    ).all()
    summaries: list[dict[str, Any]] = []

    for publisher in publishers:
        for channel in publisher.channels:
            # E-paper channels are licensing/disposition driven, not homepage HTML probes.
            if str(channel.code).startswith("epaper"):
                assessment = db.scalar(
                    select(SourceAssessment).where(
                        SourceAssessment.source_channel_id == channel.id
                    )
                )
                if assessment is None:
                    assessment = SourceAssessment(source_channel_id=channel.id)
                    db.add(assessment)
                assessment.status = SourceAssessmentStatus.requires_license
                assessment.recommended_connector = ConnectorMethod.epaper
                assessment.legal_gate = LegalGate.pending
                assessment.epaper_available = "licensed_required"
                assessment.copyright_licensing_risk = "high"
                assessment.assessment_payload = {
                    "skipped_probe": True,
                    "reason": "epaper_channel_requires_licensing_review",
                    "legal_gate_note": "Technical probe skipped. Legal gate remains pending.",
                }
                assessment.notes = (
                    "E-paper channel: homepage HTML probe skipped. "
                    "Awaiting licensing; legal gate pending."
                )
                connector = db.scalar(
                    select(SourceConnectorConfig).where(
                        SourceConnectorConfig.source_channel_id == channel.id
                    )
                )
                if connector is None:
                    connector = SourceConnectorConfig(source_channel_id=channel.id)
                    db.add(connector)
                connector.connector_type = ConnectorMethod.epaper
                connector.enabled = False
                connector.config = {
                    "phase": 8,
                    "ingestion_enabled": False,
                    "requires_legal_gate": True,
                    "requires_license": True,
                }
                row: dict[str, Any] = {
                    "publisher_code": publisher.code,
                    "channel_code": channel.code,
                    "base_url": channel.base_url,
                    "status": assessment.status.value,
                    "recommended_connector": ConnectorMethod.epaper.value,
                    "legal_gate": LegalGate.pending.value,
                    "rss_feeds": [],
                    "sitemap_urls": [],
                    "robots_allows_fetch": "unknown",
                    "homepage_status": None,
                    "errors": [],
                }
                summaries.append(row)
                if write_docs:
                    _write_assessment_doc(publisher, channel, row)
                db.commit()
                continue

            try:
                probe = assess_source(channel.base_url)
            except Exception as exc:  # noqa: BLE001 - isolate per-channel failures
                from newsfetcher_connectors.assessment import AssessmentProbeResult

                probe = AssessmentProbeResult(
                    status="temporarily_broken",
                    recommended_connector="pending",
                    errors=[str(exc)],
                    raw={"errors": [str(exc)]},
                )

            assessment = db.scalar(
                select(SourceAssessment).where(SourceAssessment.source_channel_id == channel.id)
            )
            if assessment is None:
                assessment = SourceAssessment(source_channel_id=channel.id)
                db.add(assessment)

            try:
                status = SourceAssessmentStatus(probe.status)
            except ValueError:
                status = SourceAssessmentStatus.pending_assessment
            try:
                recommended = ConnectorMethod(probe.recommended_connector)
            except ValueError:
                recommended = ConnectorMethod.pending

            assessment.status = status
            assessment.robots_txt_url = probe.robots_txt_url
            assessment.robots_allows_fetch = probe.robots_allows_fetch
            assessment.rss_available = probe.rss_available
            assessment.sitemap_available = probe.sitemap_available
            assessment.auth_paywall_status = probe.auth_paywall_status
            assessment.recommended_connector = recommended
            # Legal approval is an operational gate — never auto-approved by probes.
            assessment.legal_gate = LegalGate.pending
            assessment.assessed_at = datetime.now(UTC)
            assessment.assessment_payload = {
                **probe.raw,
                "errors": probe.errors,
                "robots_notes": probe.robots_notes,
                "rss_feeds": probe.rss_feeds,
                "sitemap_urls": probe.sitemap_urls,
                "legal_gate_note": "Technical probe only. Legal gate remains pending.",
            }
            assessment.notes = (
                f"Technical assessment {assessment.assessed_at.isoformat()}. "
                f"Recommended connector={recommended.value}. Legal gate pending."
            )
            assessment.copyright_licensing_risk = (
                "high" if probe.auth_paywall_status == "hard" else "unknown"
            )

            connector = db.scalar(
                select(SourceConnectorConfig).where(
                    SourceConnectorConfig.source_channel_id == channel.id
                )
            )
            if connector is None:
                connector = SourceConnectorConfig(source_channel_id=channel.id)
                db.add(connector)
            connector.connector_type = recommended
            connector.enabled = False
            connector.config = {
                "phase": 1,
                "ingestion_enabled": False,
                "feed_urls": probe.rss_feeds,
                "sitemap_urls": probe.sitemap_urls,
                "requires_legal_gate": True,
            }

            row = {
                "publisher_code": publisher.code,
                "channel_code": channel.code,
                "base_url": channel.base_url,
                "status": status.value,
                "recommended_connector": recommended.value,
                "legal_gate": LegalGate.pending.value,
                "rss_feeds": probe.rss_feeds,
                "sitemap_urls": probe.sitemap_urls,
                "robots_allows_fetch": probe.robots_allows_fetch,
                "homepage_status": probe.homepage_status,
                "errors": probe.errors,
            }
            summaries.append(row)
            if write_docs:
                _write_assessment_doc(publisher, channel, row)
            db.commit()

    return summaries



def shortlist_technically_ready(
    summaries: list[dict[str, Any]], *, limit: int = 4
) -> list[dict[str, Any]]:
    """Prefer RSS + robots-allowed + no hard paywall. Still legally pending."""
    ranked: list[tuple[int, dict[str, Any]]] = []
    for row in summaries:
        score = 0
        if row["recommended_connector"] == "rss":
            score += 100
        elif row["recommended_connector"] == "sitemap":
            score += 70
        elif row["recommended_connector"] == "html":
            score += 40
        if row["robots_allows_fetch"] == "yes":
            score += 20
        if row["status"] in {"approved_for_rss", "approved_for_html_fetch"}:
            score += 10
        if row["status"] in {"blocked_by_paywall", "disabled", "temporarily_broken"}:
            score -= 100
        ranked.append((score, row))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [row for score, row in ranked if score > 0][:limit]


def _write_assessment_doc(
    publisher: Publisher, channel: SourceChannel, row: dict[str, Any]
) -> None:
    DOCS_SOURCES.mkdir(parents=True, exist_ok=True)
    path = DOCS_SOURCES / f"{publisher.code}__{channel.code}.yaml"
    payload = {
        "publisher": {
            "code": publisher.code,
            "name_en": publisher.name_en,
            "name_ar": publisher.name_ar,
            "homepage": publisher.homepage_url,
        },
        "channel": {
            "code": channel.code,
            "language": str(getattr(channel.language, "value", channel.language)),
            "base_url": channel.base_url,
        },
        "assessment": {
            "status": row["status"],
            "legal_gate": "pending",
            "recommended_connector": row["recommended_connector"],
            "robots_allows_fetch": row["robots_allows_fetch"],
            "rss": {"available": bool(row["rss_feeds"]), "feeds": row["rss_feeds"]},
            "sitemap": {"available": bool(row["sitemap_urls"]), "urls": row["sitemap_urls"]},
            "homepage_status": row["homepage_status"],
            "errors": row["errors"],
            "notes": "Auto-generated technical probe. Not a legal approval.",
        },
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
