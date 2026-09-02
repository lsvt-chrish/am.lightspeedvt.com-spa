"""add monday_production_snapshot table for AI Production dashboard

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "monday_production_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("board_id", sa.String(length=64), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_monday_production_snapshot_board_id", "monday_production_snapshot", ["board_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_monday_production_snapshot_board_id", table_name="monday_production_snapshot")
    op.drop_table("monday_production_snapshot")
