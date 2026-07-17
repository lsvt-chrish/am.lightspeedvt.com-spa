"""
Derived views over the monday_event log: current per-department bucket counts
and a weekly-or-monthly trend series (new / open / pending / closed) for the
ops dashboard. The event log is the source of truth; nothing here is stored
separately from it.
"""
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MondayEvent
from app.db.session import get_db

router = APIRouter(prefix="/ops-dashboard", tags=["monday"])

BUCKETS = ("open", "new", "pending", "closed")
Period = Literal["week", "month"]


async def _bucket_counts_as_of(
    db: AsyncSession, department: str, as_of: datetime
) -> dict[str, int]:
    """
    Current bucket per item = the bucket on that item's most recent event at or
    before `as_of`. Counts items per bucket for a department as of that time
    (a snapshot, so it naturally includes anything rolled over from prior periods).
    """
    latest_ids = (
        select(
            MondayEvent.item_id,
            func.max(MondayEvent.id).label("latest_id"),
        )
        .where(MondayEvent.department == department, MondayEvent.occurred_at <= as_of)
        .group_by(MondayEvent.item_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(MondayEvent.bucket, func.count())
            .join(latest_ids, MondayEvent.id == latest_ids.c.latest_id)
            .where(MondayEvent.bucket.isnot(None))
            .group_by(MondayEvent.bucket)
        )
    ).all()
    counts = {b: 0 for b in BUCKETS}
    for bucket, count in rows:
        if bucket in counts:
            counts[bucket] = count
    return counts


async def _period_flow_counts(
    db: AsyncSession, department: str, period_start: datetime, period_end: datetime
) -> dict[str, int]:
    """New items created, and items that transitioned into "closed", within [period_start, period_end)."""
    new_count = await db.scalar(
        select(func.count()).where(
            MondayEvent.department == department,
            MondayEvent.event_type == "created",
            MondayEvent.occurred_at >= period_start,
            MondayEvent.occurred_at < period_end,
        )
    )
    closed_count = await db.scalar(
        select(func.count()).where(
            MondayEvent.department == department,
            MondayEvent.bucket == "closed",
            MondayEvent.occurred_at >= period_start,
            MondayEvent.occurred_at < period_end,
        )
    )
    return {"new": new_count or 0, "closed": closed_count or 0}


def _shift_months(dt: datetime, delta: int) -> datetime:
    """Return the 1st-of-month, delta months from dt's month (delta may be negative)."""
    total = dt.year * 12 + (dt.month - 1) + delta
    year, month = divmod(total, 12)
    return dt.replace(year=year, month=month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


def _period_boundaries(period: Period, count: int) -> list[tuple[datetime, datetime]]:
    """Return `count` consecutive (start, end) UTC boundaries, oldest first, ending now."""
    now = datetime.now(tz=timezone.utc)
    if period == "week":
        end = now
        bounds = []
        for _ in range(count):
            start = end - timedelta(days=7)
            bounds.append((start, end))
            end = start
        return list(reversed(bounds))

    # period == "month": calendar-month boundaries; the most recent one is a
    # partial month running from the 1st through now.
    current_month_start = _shift_months(now, 0)
    bounds = []
    for i in range(count):
        start = _shift_months(current_month_start, -i)
        end = now if i == 0 else _shift_months(current_month_start, -i + 1)
        bounds.append((start, end))
    return list(reversed(bounds))


class PeriodPoint(BaseModel):
    period_start: datetime
    period_end: datetime
    open: int
    new: int
    pending: int
    closed: int


class DepartmentTrend(BaseModel):
    department: str
    period: Period
    points: list[PeriodPoint]


@router.get("/trend", response_model=DepartmentTrend)
async def get_trend(
    department: str,
    period: Period = "week",
    count: int = 8,
    db: AsyncSession = Depends(get_db),
):
    if count < 1 or count > 104:
        raise HTTPException(status_code=400, detail="count must be between 1 and 104")
    points: list[PeriodPoint] = []
    for period_start, period_end in _period_boundaries(period, count):
        snapshot = await _bucket_counts_as_of(db, department, period_end)
        flow = await _period_flow_counts(db, department, period_start, period_end)
        points.append(
            PeriodPoint(
                period_start=period_start,
                period_end=period_end,
                open=snapshot["open"],
                new=flow["new"],
                pending=snapshot["pending"],
                closed=flow["closed"],
            )
        )
    return DepartmentTrend(department=department, period=period, points=points)


class CurrentCounts(BaseModel):
    department: str
    open: int
    pending: int


@router.get("/current", response_model=list[CurrentCounts])
async def get_current(db: AsyncSession = Depends(get_db)):
    departments = (
        await db.scalars(
            select(MondayEvent.department).where(MondayEvent.department.isnot(None)).distinct()
        )
    ).all()
    now = datetime.now(tz=timezone.utc)
    out = []
    for department in departments:
        snapshot = await _bucket_counts_as_of(db, department, now)
        out.append(CurrentCounts(department=department, open=snapshot["open"], pending=snapshot["pending"]))
    return out
