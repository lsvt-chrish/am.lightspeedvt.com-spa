"""ORM models for the Monday.com ops dashboard event log."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MondayBoard(Base):
    """
    Per-board config: which department a board belongs to, and how its groups
    (and, optionally, status column values) map onto the four canonical buckets
    used across the dashboard: open, new, pending, closed.

    bucket_map shape: {"groups": {"<group name>": "<bucket>"}, "statuses": {"<status label>": "<bucket>"}}
    Group mapping is checked first (matches the SA Tasks board export, where the
    group name alone was enough); statuses are a fallback for boards that bucket
    by status column instead of by group.
    """

    __tablename__ = "monday_board"

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    department: Mapped[str] = mapped_column(String(100), index=True)
    bucket_map: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    events: Mapped[list["MondayEvent"]] = relationship(back_populates="board")


class MondayEvent(Base):
    """
    Append-only log of Monday.com item lifecycle events (item created, status
    changed), as delivered by a Monday.com automation webhook. This is the
    source of truth; current counts and trend charts are derived queries over
    this table rather than separately-maintained snapshots.
    """

    __tablename__ = "monday_event"
    __table_args__ = (
        Index("ix_monday_event_board_occurred", "board_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("monday_board.board_id"), index=True
    )
    item_id: Mapped[str] = mapped_column(String(64), index=True)
    item_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    event_type: Mapped[str] = mapped_column(String(32))  # "created" | "status_changed"
    group_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    group_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    column_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    previous_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Resolved at ingest time via the board's bucket_map, for cheap querying.
    department: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    bucket: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    raw_payload: Mapped[dict] = mapped_column(JSON)

    board: Mapped["MondayBoard"] = relationship(back_populates="events")
