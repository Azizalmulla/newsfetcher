from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.arabic import normalize_text
from app.core.deps import AuthContext, get_current_auth, require_roles, tenant_scoped_get
from app.db.session import get_db
from app.models.monitoring import MonitoringAlias, MonitoringEntity, MonitoringExclusion
from app.services.audit import write_audit

router = APIRouter(prefix="/entities", tags=["entities"])

ALLOWED_TYPES = {
    "brand",
    "company",
    "competitor",
    "product",
    "executive",
    "campaign",
    "industry_topic",
    "project",
    "government_entity",
}


class AliasIn(BaseModel):
    alias_text: str = Field(min_length=1, max_length=512)
    language: str = Field(pattern=r"^(ar|en)$")
    exact_only: bool = False


class ExclusionIn(BaseModel):
    phrase: str = Field(min_length=1, max_length=512)
    language: str = "both"


class EntityCreate(BaseModel):
    entity_type: str
    canonical_name_ar: str | None = None
    canonical_name_en: str | None = None
    language_preference: str = "both"
    semantic_instruction: str | None = None
    aliases: list[AliasIn] = Field(default_factory=list)
    exclusions: list[ExclusionIn] = Field(default_factory=list)


class AliasOut(BaseModel):
    id: UUID
    alias_text: str
    alias_normalized: str
    language: str
    exact_only: bool


class ExclusionOut(BaseModel):
    id: UUID
    phrase: str
    phrase_normalized: str
    language: str


class EntityOut(BaseModel):
    id: UUID
    entity_type: str
    canonical_name_ar: str | None
    canonical_name_en: str | None
    language_preference: str
    semantic_instruction: str | None
    is_active: bool
    aliases: list[AliasOut]
    exclusions: list[ExclusionOut]


def _to_out(entity: MonitoringEntity) -> EntityOut:
    return EntityOut(
        id=entity.id,
        entity_type=entity.entity_type,
        canonical_name_ar=entity.canonical_name_ar,
        canonical_name_en=entity.canonical_name_en,
        language_preference=entity.language_preference,
        semantic_instruction=entity.semantic_instruction,
        is_active=entity.is_active,
        aliases=[
            AliasOut(
                id=alias.id,
                alias_text=alias.alias_text,
                alias_normalized=alias.alias_normalized,
                language=alias.language,
                exact_only=alias.exact_only,
            )
            for alias in entity.aliases
        ],
        exclusions=[
            ExclusionOut(
                id=excl.id,
                phrase=excl.phrase,
                phrase_normalized=excl.phrase_normalized,
                language=excl.language,
            )
            for excl in entity.exclusions
        ],
    )


@router.get("", response_model=list[EntityOut])
def list_entities(
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[EntityOut]:
    entities = db.scalars(
        select(MonitoringEntity)
        .where(MonitoringEntity.tenant_id == auth.tenant_id)
        .options(
            selectinload(MonitoringEntity.aliases),
            selectinload(MonitoringEntity.exclusions),
        )
        .order_by(MonitoringEntity.created_at.desc())
    ).all()
    return [_to_out(entity) for entity in entities]


@router.post("", response_model=EntityOut, status_code=201)
def create_entity(
    payload: EntityCreate,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> EntityOut:
    if payload.entity_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Invalid entity_type")
    if not payload.canonical_name_ar and not payload.canonical_name_en:
        raise HTTPException(status_code=400, detail="At least one canonical name required")

    entity = MonitoringEntity(
        tenant_id=auth.tenant_id,
        entity_type=payload.entity_type,
        canonical_name_ar=payload.canonical_name_ar,
        canonical_name_en=payload.canonical_name_en,
        language_preference=payload.language_preference,
        semantic_instruction=payload.semantic_instruction,
        is_active=True,
    )
    db.add(entity)
    db.flush()

    for alias in payload.aliases:
        db.add(
            MonitoringAlias(
                tenant_id=auth.tenant_id,
                entity_id=entity.id,
                alias_text=alias.alias_text,
                alias_normalized=normalize_text(alias.alias_text),
                language=alias.language,
                exact_only=alias.exact_only,
            )
        )
    for excl in payload.exclusions:
        db.add(
            MonitoringExclusion(
                tenant_id=auth.tenant_id,
                entity_id=entity.id,
                phrase=excl.phrase,
                phrase_normalized=normalize_text(excl.phrase),
                language=excl.language,
            )
        )

    write_audit(
        db,
        tenant_id=auth.tenant_id,
        actor_id=str(auth.user.id),
        action="entity.created",
        resource_type="monitoring_entity",
        resource_id=str(entity.id),
        details={"entity_type": entity.entity_type},
    )
    entity_id = entity.id
    db.commit()
    loaded = db.scalar(
        select(MonitoringEntity)
        .where(MonitoringEntity.id == entity_id)
        .options(
            selectinload(MonitoringEntity.aliases),
            selectinload(MonitoringEntity.exclusions),
        )
    )
    assert loaded is not None
    return _to_out(loaded)


@router.get("/{entity_id}", response_model=EntityOut)
def get_entity(
    entity_id: UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> EntityOut:
    entity = tenant_scoped_get(MonitoringEntity, db, auth, entity_id)
    loaded = db.scalar(
        select(MonitoringEntity)
        .where(MonitoringEntity.id == entity.id)
        .options(
            selectinload(MonitoringEntity.aliases),
            selectinload(MonitoringEntity.exclusions),
        )
    )
    assert loaded is not None
    return _to_out(loaded)


@router.delete("/{entity_id}", status_code=204)
def delete_entity(
    entity_id: UUID,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> None:
    entity = tenant_scoped_get(MonitoringEntity, db, auth, entity_id)
    write_audit(
        db,
        tenant_id=auth.tenant_id,
        actor_id=str(auth.user.id),
        action="entity.deleted",
        resource_type="monitoring_entity",
        resource_id=str(entity.id),
    )
    db.delete(entity)
    db.commit()
