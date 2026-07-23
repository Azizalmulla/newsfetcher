"""Idempotent seed for Phase 0 source registry and role skeleton."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.seed_data import INITIAL_ROLES, MANDATORY_PUBLISHERS
from app.db.session import SessionLocal
from app.models.enums import (
    ChannelLanguage,
    ConnectorMethod,
    LegalGate,
    SourceAssessmentStatus,
)
from app.models.sources import Publisher, SourceAssessment, SourceChannel, SourceConnectorConfig
from app.models.tenancy import Role

logger = logging.getLogger(__name__)


def seed_roles(db: Session) -> int:
    created = 0
    for role_data in INITIAL_ROLES:
        existing = db.scalar(select(Role).where(Role.code == role_data["code"]))
        if existing:
            continue
        db.add(
            Role(
                code=role_data["code"],
                name=role_data["name"],
                description=role_data["description"],
            )
        )
        created += 1
    return created


def seed_publishers(db: Session) -> tuple[int, int]:
    publishers_created = 0
    channels_created = 0

    for publisher_data in MANDATORY_PUBLISHERS:
        publisher = db.scalar(select(Publisher).where(Publisher.code == publisher_data["code"]))
        if publisher is None:
            publisher = Publisher(
                code=publisher_data["code"],
                name_en=publisher_data["name_en"],
                name_ar=publisher_data["name_ar"],
                homepage_url=publisher_data["homepage_url"],
                media_type=publisher_data["media_type"],
                is_mandatory=True,
            )
            db.add(publisher)
            db.flush()
            publishers_created += 1

        for channel_data in publisher_data["channels"]:
            channel = db.scalar(
                select(SourceChannel).where(
                    SourceChannel.publisher_id == publisher.id,
                    SourceChannel.code == channel_data["code"],
                )
            )
            if channel is None:
                channel = SourceChannel(
                    publisher_id=publisher.id,
                    code=channel_data["code"],
                    label=channel_data["label"],
                    language=ChannelLanguage(channel_data["language"]),
                    base_url=channel_data["base_url"],
                    is_active=False,
                )
                db.add(channel)
                db.flush()
                channels_created += 1

            assessment = db.scalar(
                select(SourceAssessment).where(SourceAssessment.source_channel_id == channel.id)
            )
            if assessment is None:
                db.add(
                    SourceAssessment(
                        source_channel_id=channel.id,
                        status=SourceAssessmentStatus.pending_assessment,
                        recommended_connector=ConnectorMethod.pending,
                        legal_gate=LegalGate.pending,
                        assessment_payload={
                            "robots_txt": {"status": "unknown"},
                            "rss": {"available": "unknown"},
                            "sitemap": {"available": "unknown"},
                            "public_api": {"available": "unknown"},
                            "epaper": {"available": "unknown"},
                            "notes": "Phase 0 registry seed; assessment pending.",
                        },
                        notes=(
                            "Seeded in Phase 0. Do not scrape until assessment "
                            "and legal gate pass."
                        ),
                    )
                )

            connector = db.scalar(
                select(SourceConnectorConfig).where(
                    SourceConnectorConfig.source_channel_id == channel.id
                )
            )
            if connector is None:
                db.add(
                    SourceConnectorConfig(
                        source_channel_id=channel.id,
                        connector_type=ConnectorMethod.pending,
                        enabled=False,
                        config={"phase": 0, "ingestion_enabled": False},
                    )
                )

    return publishers_created, channels_created


def run_seed() -> dict[str, int]:
    db = SessionLocal()
    try:
        roles_created = seed_roles(db)
        publishers_created, channels_created = seed_publishers(db)
        db.commit()
        from app.services.source_closure import apply_source_closure

        closure = apply_source_closure(db, actor_id="seed")
        from app.services.social import seed_outlet_accounts

        social_accounts = seed_outlet_accounts(db)
        result = {
            "roles_created": roles_created,
            "publishers_created": publishers_created,
            "channels_created": channels_created,
            "phase8_closed": closure["applied"],
            "social_accounts_seeded": social_accounts,
        }
        logger.info("Seed complete: %s", result)
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    result = run_seed()
    print(result)


if __name__ == "__main__":
    main()
