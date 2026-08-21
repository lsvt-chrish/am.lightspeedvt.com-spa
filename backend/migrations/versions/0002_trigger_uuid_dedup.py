"""add trigger_uuid to monday_event for webhook retry dedup

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("monday_event", sa.Column("trigger_uuid", sa.String(length=64), nullable=True))
    op.create_index(
        "ix_monday_event_trigger_uuid", "monday_event", ["trigger_uuid"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_monday_event_trigger_uuid", table_name="monday_event")
    op.drop_column("monday_event", "trigger_uuid")
