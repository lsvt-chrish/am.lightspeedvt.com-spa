"""initial monday board and event tables

Revision ID: 0001
Revises:
Create Date: 2026-07-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "monday_board",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("board_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=100), nullable=False),
        sa.Column("bucket_map", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_monday_board_board_id", "monday_board", ["board_id"], unique=True)
    op.create_index("ix_monday_board_department", "monday_board", ["department"])

    op.create_table(
        "monday_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("board_id", sa.String(length=64), sa.ForeignKey("monday_board.board_id"), nullable=False),
        sa.Column("item_id", sa.String(length=64), nullable=False),
        sa.Column("item_name", sa.String(length=500), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("group_id", sa.String(length=100), nullable=True),
        sa.Column("group_name", sa.String(length=255), nullable=True),
        sa.Column("column_id", sa.String(length=100), nullable=True),
        sa.Column("previous_value", sa.String(length=255), nullable=True),
        sa.Column("new_value", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column("bucket", sa.String(length=20), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_monday_event_board_id", "monday_event", ["board_id"])
    op.create_index("ix_monday_event_item_id", "monday_event", ["item_id"])
    op.create_index("ix_monday_event_department", "monday_event", ["department"])
    op.create_index("ix_monday_event_bucket", "monday_event", ["bucket"])
    op.create_index("ix_monday_event_occurred_at", "monday_event", ["occurred_at"])
    op.create_index("ix_monday_event_board_occurred", "monday_event", ["board_id", "occurred_at"])


def downgrade() -> None:
    op.drop_table("monday_event")
    op.drop_table("monday_board")
