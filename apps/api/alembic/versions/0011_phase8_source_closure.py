"""Phase 8 source disposition + recovery plans.

Revision ID: 0011_phase8_source_closure
Revises: 0010_phase7_epaper
Create Date: 2026-07-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_phase8_source_closure"
down_revision: Union[str, None] = "0010_phase7_epaper"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "source_assessments",
        sa.Column("phase8_disposition", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_source_assessments_phase8_disposition",
        "source_assessments",
        ["phase8_disposition"],
    )
    op.add_column(
        "source_assessments",
        sa.Column(
            "recovery_plan",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "source_assessments",
        sa.Column("closure_notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("source_assessments", "closure_notes")
    op.drop_column("source_assessments", "recovery_plan")
    op.drop_index("ix_source_assessments_phase8_disposition", table_name="source_assessments")
    op.drop_column("source_assessments", "phase8_disposition")
