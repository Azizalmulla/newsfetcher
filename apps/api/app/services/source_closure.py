"""Apply Phase 8 source closure matrix without enabling live ingestion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import ConnectorMethod, LegalGate, SourceAssessmentStatus
from app.models.sources import Publisher, SourceAssessment, SourceChannel, SourceConnectorConfig
from app.services.audit import write_audit

# Prefer packaged copy (Docker image), fall back to monorepo docs path locally.
_PACKAGED_MATRIX = (
    Path(__file__).resolve().parents[1] / "data" / "PHASE8_SOURCE_CLOSURE_MATRIX.yaml"
)
_DOCS_MATRIX = (
    Path(__file__).resolve().parents[4] / "docs" / "sources" / "PHASE8_SOURCE_CLOSURE_MATRIX.yaml"
)
MATRIX_PATH = _PACKAGED_MATRIX if _PACKAGED_MATRIX.is_file() else _DOCS_MATRIX
VALID_DISPOSITIONS = frozenset(
    {"active", "blocked", "awaiting_licensing", "temporarily_broken"}
)


def load_closure_matrix(path: Path | None = None) -> dict[str, Any]:
    matrix_path = path or MATRIX_PATH
    payload = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "channels" not in payload:
        raise ValueError("Invalid Phase 8 closure matrix")
    return payload


def apply_source_closure(
    db: Session,
    *,
    actor_id: str | None = None,
    matrix_path: Path | None = None,
) -> dict[str, Any]:
    matrix = load_closure_matrix(matrix_path)
    rows = matrix.get("channels") or []
    applied = 0
    missing: list[str] = []
    summaries: list[dict[str, Any]] = []

    for row in rows:
        publisher_code = str(row["publisher"])
        channel_code = str(row["channel"])
        disposition = str(row["disposition"])
        if disposition not in VALID_DISPOSITIONS:
            raise ValueError(f"Invalid disposition for {publisher_code}/{channel_code}")

        publisher = db.scalar(select(Publisher).where(Publisher.code == publisher_code))
        if publisher is None:
            missing.append(f"{publisher_code}/{channel_code}:publisher")
            continue
        channel = db.scalar(
            select(SourceChannel).where(
                SourceChannel.publisher_id == publisher.id,
                SourceChannel.code == channel_code,
            )
        )
        if channel is None:
            missing.append(f"{publisher_code}/{channel_code}:channel")
            continue

        assessment = db.scalar(
            select(SourceAssessment).where(SourceAssessment.source_channel_id == channel.id)
        )
        if assessment is None:
            assessment = SourceAssessment(source_channel_id=channel.id)
            db.add(assessment)

        status = SourceAssessmentStatus(str(row["assessment_status"]))
        recommended = ConnectorMethod(str(row["recommended_connector"]))
        assessment.status = status
        assessment.recommended_connector = recommended
        # Never auto-approve legal gates from closure apply.
        if assessment.legal_gate != LegalGate.blocked:
            assessment.legal_gate = LegalGate.pending
        assessment.phase8_disposition = disposition
        assessment.recovery_plan = row.get("recovery_plan") or {}
        assessment.closure_notes = row.get("notes")
        if disposition == "awaiting_licensing":
            assessment.epaper_available = "licensed_required"
            assessment.copyright_licensing_risk = "high"
        elif recommended == ConnectorMethod.epaper and disposition == "active":
            assessment.epaper_available = "public"
            assessment.copyright_licensing_risk = "low"

        connector = db.scalar(
            select(SourceConnectorConfig).where(
                SourceConnectorConfig.source_channel_id == channel.id
            )
        )
        if connector is None:
            connector = SourceConnectorConfig(source_channel_id=channel.id)
            db.add(connector)
        connector.connector_type = recommended
        connector.enabled = False  # hard rule for Phase 8 apply
        config = dict(row.get("connector_config") or {})
        config["phase"] = 8
        config["ingestion_enabled"] = False
        config["requires_legal_gate"] = True
        config["phase8_disposition"] = disposition
        connector.config = config
        if disposition == "active" and recommended == ConnectorMethod.html:
            connector.politeness_delay_ms = max(connector.politeness_delay_ms, 1500)

        # Channel active flag means monitored — not that scraping is live.
        channel.is_active = disposition in {"active", "temporarily_broken", "awaiting_licensing"}

        applied += 1
        summaries.append(
            {
                "publisher": publisher_code,
                "channel": channel_code,
                "disposition": disposition,
                "assessment_status": status.value,
                "recommended_connector": recommended.value,
                "legal_gate": str(
                    getattr(assessment.legal_gate, "value", assessment.legal_gate)
                ),
                "connector_enabled": False,
                "has_recovery_plan": bool(assessment.recovery_plan),
            }
        )

    write_audit(
        db,
        tenant_id=None,
        actor_id=actor_id,
        action="sources.phase8_closure_applied",
        resource_type="source_closure",
        resource_id="phase8",
        details={"applied": applied, "missing": missing, "matrix_version": matrix.get("version")},
    )
    db.commit()
    return {
        "applied": applied,
        "missing": missing,
        "expected": len(rows),
        "enabled_connectors": 0,
        "legal_gates_approved": 0,
        "channels": summaries,
        "disposition_counts": _count_dispositions(summaries),
    }


def list_source_closure(db: Session) -> dict[str, Any]:
    publishers = db.scalars(
        select(Publisher)
        .options(
            selectinload(Publisher.channels).selectinload(SourceChannel.assessment),
            selectinload(Publisher.channels).selectinload(SourceChannel.connector_config),
        )
        .order_by(Publisher.code)
    ).all()
    channels: list[dict[str, Any]] = []
    for publisher in publishers:
        for channel in publisher.channels:
            assessment = channel.assessment
            connector = channel.connector_config
            channels.append(
                {
                    "publisher": publisher.code,
                    "channel": channel.code,
                    "disposition": assessment.phase8_disposition if assessment else None,
                    "assessment_status": (
                        str(getattr(assessment.status, "value", assessment.status))
                        if assessment
                        else None
                    ),
                    "legal_gate": (
                        str(getattr(assessment.legal_gate, "value", assessment.legal_gate))
                        if assessment
                        else None
                    ),
                    "recommended_connector": (
                        str(
                            getattr(
                                assessment.recommended_connector,
                                "value",
                                assessment.recommended_connector,
                            )
                        )
                        if assessment
                        else None
                    ),
                    "connector_enabled": bool(connector.enabled) if connector else False,
                    "recovery_plan": assessment.recovery_plan if assessment else {},
                    "closure_notes": assessment.closure_notes if assessment else None,
                    "is_active": channel.is_active,
                }
            )
    open_items = [
        row
        for row in channels
        if row["disposition"] is None or row["disposition"] not in VALID_DISPOSITIONS
    ]
    return {
        "channel_count": len(channels),
        "closed_count": len(channels) - len(open_items),
        "open_count": len(open_items),
        "enabled_connectors": sum(1 for row in channels if row["connector_enabled"]),
        "disposition_counts": _count_dispositions(channels),
        "channels": channels,
        "open_items": open_items,
        "phase8_complete": len(open_items) == 0 and len(channels) > 0,
    }


def matrix_covers_all_seed_channels() -> tuple[bool, list[str]]:
    from app.db.seed_data import MANDATORY_PUBLISHERS

    matrix = load_closure_matrix()
    expected = {
        (publisher["code"], channel["code"])
        for publisher in MANDATORY_PUBLISHERS
        for channel in publisher["channels"]
    }
    actual = {(str(row["publisher"]), str(row["channel"])) for row in matrix["channels"]}
    missing = sorted(f"{p}/{c}" for p, c in (expected - actual))
    extra = sorted(f"{p}/{c}" for p, c in (actual - expected))
    ok = not missing and not extra
    problems = [f"missing:{item}" for item in missing] + [f"extra:{item}" for item in extra]
    return ok, problems


def _count_dispositions(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {key: 0 for key in sorted(VALID_DISPOSITIONS)}
    counts["unset"] = 0
    for row in rows:
        key = row.get("disposition") or "unset"
        counts[key] = counts.get(key, 0) + 1
    return counts
