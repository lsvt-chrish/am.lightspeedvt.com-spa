"""
Derived views over the monday_event log: current per-department bucket counts
and a weekly-or-monthly trend series (new / open / pending / closed) for the
ops dashboard. The event log is the source of truth; nothing here is stored
separately from it.

Trend/current queries can be narrowed with optional board_id / group_name /
status filters on top of the department filter, and the trend range can be
given either as "last N weeks/months" or an explicit start/end date range.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import MONDAY_ACCOUNT_SUBDOMAIN
from app.db.models import MondayBoard, MondayEvent
from app.db.session import get_db

router = APIRouter(prefix="/ops-dashboard", tags=["monday"])

BUCKETS = ("open", "new", "pending", "closed", "excluded")
Period = Literal["day", "week", "month"]


def _apply_scope_filters(stmt, department, board_id, group_name, status_label):
    if department is not None:
        stmt = stmt.where(MondayEvent.department == department)
    if board_id is not None:
        stmt = stmt.where(MondayEvent.board_id == board_id)
    if group_name is not None:
        stmt = stmt.where(MondayEvent.group_name == group_name)
    if status_label is not None:
        stmt = stmt.where(MondayEvent.new_value == status_label)
    return stmt


async def _bucket_counts_as_of(
    db: AsyncSession,
    as_of: datetime,
    department: str | None = None,
    board_id: str | None = None,
    group_name: str | None = None,
    status_label: str | None = None,
) -> dict[str, int]:
    """
    Current bucket per item = the bucket on that item's most recent event at or
    before `as_of` (optionally narrowed by board/group/status). Counts items
    per bucket as of that time -- a snapshot, so it naturally includes
    anything rolled over from prior periods.
    """
    latest_ids_stmt = (
        select(
            MondayEvent.item_id,
            func.max(MondayEvent.id).label("latest_id"),
        )
        .where(MondayEvent.occurred_at <= as_of)
        .group_by(MondayEvent.item_id)
    )
    latest_ids_stmt = _apply_scope_filters(latest_ids_stmt, department, board_id, group_name, status_label)
    latest_ids = latest_ids_stmt.subquery()

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
    db: AsyncSession,
    period_start: datetime,
    period_end: datetime,
    department: str | None = None,
    board_id: str | None = None,
    group_name: str | None = None,
    status_label: str | None = None,
) -> dict[str, int]:
    """New items created, and items that transitioned into "closed", within [period_start, period_end)."""
    new_stmt = select(func.count()).where(
        MondayEvent.event_type == "created",
        MondayEvent.occurred_at >= period_start,
        MondayEvent.occurred_at < period_end,
    )
    new_stmt = _apply_scope_filters(new_stmt, department, board_id, group_name, status_label)
    new_count = await db.scalar(new_stmt)

    closed_stmt = select(func.count()).where(
        MondayEvent.bucket == "closed",
        MondayEvent.occurred_at >= period_start,
        MondayEvent.occurred_at < period_end,
    )
    closed_stmt = _apply_scope_filters(closed_stmt, department, board_id, group_name, status_label)
    closed_count = await db.scalar(closed_stmt)

    return {"new": new_count or 0, "closed": closed_count or 0}


def _shift_months(dt: datetime, delta: int) -> datetime:
    """Return the 1st-of-month, delta months from dt's month (delta may be negative)."""
    total = dt.year * 12 + (dt.month - 1) + delta
    year, month = divmod(total, 12)
    return dt.replace(year=year, month=month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


Compare = Literal["previous_day", "previous_week", "previous_month"]


def _shift_range(start: datetime, end: datetime, compare: Compare) -> tuple[datetime, datetime]:
    """Shift a [start, end) window back by a fixed offset for period-over-period comparison."""
    if compare == "previous_day":
        delta = timedelta(days=1)
        return start - delta, end - delta
    if compare == "previous_week":
        delta = timedelta(days=7)
        return start - delta, end - delta
    return _shift_months(start, -1), _shift_months(end, -1)


def _period_boundaries(
    period: Period,
    count: int = 8,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[tuple[datetime, datetime]]:
    """
    Return consecutive (start, end) UTC boundaries, oldest first.
    If start/end are given, cover exactly that range; otherwise return the
    last `count` periods ending now.
    """
    if start is not None and end is not None:
        bounds: list[tuple[datetime, datetime]] = []
        if period == "day":
            cur = start
            while cur < end:
                nxt = min(cur + timedelta(days=1), end)
                bounds.append((cur, nxt))
                cur = nxt
        elif period == "week":
            cur = start
            while cur < end:
                nxt = min(cur + timedelta(days=7), end)
                bounds.append((cur, nxt))
                cur = nxt
        else:
            cur = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            while cur < end:
                nxt = _shift_months(cur, 1)
                bounds.append((max(cur, start), min(nxt, end)))
                cur = nxt
        return bounds

    now = datetime.now(tz=timezone.utc)
    if period == "day":
        end = now
        bounds = []
        for _ in range(count):
            s = end - timedelta(days=1)
            bounds.append((s, end))
            end = s
        return list(reversed(bounds))

    if period == "week":
        end = now
        bounds = []
        for _ in range(count):
            s = end - timedelta(days=7)
            bounds.append((s, end))
            end = s
        return list(reversed(bounds))

    # period == "month": calendar-month boundaries; the most recent one is a
    # partial month running from the 1st through now.
    current_month_start = _shift_months(now, 0)
    bounds = []
    for i in range(count):
        s = _shift_months(current_month_start, -i)
        e = now if i == 0 else _shift_months(current_month_start, -i + 1)
        bounds.append((s, e))
    return list(reversed(bounds))


class PeriodPoint(BaseModel):
    period_start: datetime
    period_end: datetime
    open: int
    new: int
    pending: int
    closed: int
    excluded: int


class DepartmentTrend(BaseModel):
    department: str | None
    period: Period
    points: list[PeriodPoint]
    previous_points: list[PeriodPoint] | None = None


def _to_utc_datetime(d: date, end_of_day: bool = False) -> datetime:
    dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return dt + timedelta(days=1) if end_of_day else dt


async def _build_points(
    db: AsyncSession,
    boundaries: list[tuple[datetime, datetime]],
    department: str | None,
    board_id: str | None,
    group: str | None,
    status: str | None,
) -> list[PeriodPoint]:
    points: list[PeriodPoint] = []
    for period_start, period_end in boundaries:
        snapshot = await _bucket_counts_as_of(db, period_end, department, board_id, group, status)
        flow = await _period_flow_counts(db, period_start, period_end, department, board_id, group, status)
        points.append(
            PeriodPoint(
                period_start=period_start,
                period_end=period_end,
                open=snapshot["open"],
                new=flow["new"],
                pending=snapshot["pending"],
                closed=flow["closed"],
                excluded=snapshot["excluded"],
            )
        )
    return points


@router.get("/trend", response_model=DepartmentTrend)
async def get_trend(
    department: str | None = None,
    board_id: str | None = None,
    group: str | None = None,
    status: str | None = None,
    period: Period = "week",
    count: int = 8,
    start: date | None = None,
    end: date | None = None,
    compare: Compare | None = None,
    db: AsyncSession = Depends(get_db),
):
    if start is not None and end is not None:
        if start > end:
            raise HTTPException(status_code=400, detail="start must be before end")
        start_dt = _to_utc_datetime(start)
        end_dt = _to_utc_datetime(end, end_of_day=True)
        boundaries = _period_boundaries(period, start=start_dt, end=end_dt)
    else:
        if count < 1 or count > 104:
            raise HTTPException(status_code=400, detail="count must be between 1 and 104")
        boundaries = _period_boundaries(period, count=count)
        start_dt, end_dt = boundaries[0][0], boundaries[-1][1]

    points = await _build_points(db, boundaries, department, board_id, group, status)

    previous_points = None
    if compare is not None:
        prev_start, prev_end = _shift_range(start_dt, end_dt, compare)
        previous_boundaries = _period_boundaries(period, start=prev_start, end=prev_end)
        previous_points = await _build_points(db, previous_boundaries, department, board_id, group, status)

    return DepartmentTrend(department=department, period=period, points=points, previous_points=previous_points)


class LiveTotals(BaseModel):
    new: int
    open: int
    pending: int
    closed: int
    as_of: datetime


@router.get("/live-totals", response_model=LiveTotals)
async def get_live_totals(
    board_id: str | None = None,
    group: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Org-wide (all departments combined) current bucket counts, for the live snapshot section."""
    now = datetime.now(tz=timezone.utc)
    counts = await _bucket_counts_as_of(db, now, None, board_id, group, status)
    return LiveTotals(new=counts["new"], open=counts["open"], pending=counts["pending"], closed=counts["closed"], as_of=now)


class CurrentCounts(BaseModel):
    department: str
    open: int
    pending: int


@router.get("/current", response_model=list[CurrentCounts])
async def get_current(
    board_id: str | None = None,
    group: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    dept_stmt = select(MondayEvent.department).where(MondayEvent.department.isnot(None)).distinct()
    dept_stmt = _apply_scope_filters(dept_stmt, None, board_id, group, status)
    departments = (await db.scalars(dept_stmt)).all()

    now = datetime.now(tz=timezone.utc)
    out = []
    for department in departments:
        snapshot = await _bucket_counts_as_of(db, now, department, board_id, group, status)
        out.append(CurrentCounts(department=department, open=snapshot["open"], pending=snapshot["pending"]))
    return out


class BoardValues(BaseModel):
    groups: list[str]
    statuses: list[str]


class ItemRow(BaseModel):
    item_id: str
    item_name: str | None
    board_id: str
    board_name: str | None
    department: str | None
    group_name: str | None
    status: str | None
    occurred_at: datetime
    monday_url: str


def _monday_url(board_id: str, item_id: str) -> str:
    return f"https://{MONDAY_ACCOUNT_SUBDOMAIN}.monday.com/boards/{board_id}/pulses/{item_id}"


async def _backfill_item_names(db: AsyncSession, item_ids: list[str]) -> dict[str, str | None]:
    """item_name is only captured on the 'created' event; look it up for display elsewhere."""
    if not item_ids:
        return {}
    rows = (
        await db.execute(
            select(MondayEvent.item_id, MondayEvent.item_name).where(
                MondayEvent.event_type == "created", MondayEvent.item_id.in_(item_ids)
            )
        )
    ).all()
    return {item_id: name for item_id, name in rows}


@router.get("/items", response_model=list[ItemRow])
async def get_items(
    metric: Literal["open", "pending", "new", "closed"],
    period_start: datetime,
    period_end: datetime,
    department: str | None = None,
    board_id: str | None = None,
    group: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    The actual items behind one data point on a trend chart. open/pending are
    snapshots as of period_end (matching exactly how the chart line itself is
    computed); new/closed are event-based within [period_start, period_end).
    """
    board_names = dict(
        (await db.execute(select(MondayBoard.board_id, MondayBoard.name))).all()
    )

    cols = (
        MondayEvent.item_id,
        MondayEvent.board_id,
        MondayEvent.department,
        MondayEvent.group_name,
        MondayEvent.new_value,
        MondayEvent.occurred_at,
    )

    if metric in ("open", "pending"):
        latest_ids_stmt = (
            select(MondayEvent.item_id, func.max(MondayEvent.id).label("latest_id"))
            .where(MondayEvent.occurred_at <= period_end)
            .group_by(MondayEvent.item_id)
        )
        latest_ids_stmt = _apply_scope_filters(latest_ids_stmt, department, board_id, group, status)
        latest_ids = latest_ids_stmt.subquery()
        stmt = (
            select(*cols)
            .join(latest_ids, MondayEvent.id == latest_ids.c.latest_id)
            .where(MondayEvent.bucket == metric)
            .order_by(MondayEvent.occurred_at.desc())
            .limit(500)
        )
    elif metric == "new":
        stmt = (
            select(*cols)
            .where(
                MondayEvent.event_type == "created",
                MondayEvent.occurred_at >= period_start,
                MondayEvent.occurred_at < period_end,
            )
            .order_by(MondayEvent.occurred_at.desc())
            .limit(500)
        )
        stmt = _apply_scope_filters(stmt, department, board_id, group, status)
    else:  # closed
        stmt = (
            select(*cols)
            .where(
                MondayEvent.bucket == "closed",
                MondayEvent.occurred_at >= period_start,
                MondayEvent.occurred_at < period_end,
            )
            .order_by(MondayEvent.occurred_at.desc())
            .limit(500)
        )
        stmt = _apply_scope_filters(stmt, department, board_id, group, status)

    rows = (await db.execute(stmt)).all()
    names = await _backfill_item_names(db, [r.item_id for r in rows])

    return [
        ItemRow(
            item_id=r.item_id,
            item_name=names.get(r.item_id),
            board_id=r.board_id,
            board_name=board_names.get(r.board_id),
            department=r.department,
            group_name=r.group_name,
            status=r.new_value,
            occurred_at=r.occurred_at,
            monday_url=_monday_url(r.board_id, r.item_id),
        )
        for r in rows
    ]


@router.get("/board-values", response_model=BoardValues)
async def get_board_values(board_id: str, db: AsyncSession = Depends(get_db)):
    """Distinct group names and status labels ever logged for a board (mapped or not), for filter dropdowns."""
    groups = (
        await db.scalars(
            select(MondayEvent.group_name)
            .where(MondayEvent.board_id == board_id, MondayEvent.group_name.isnot(None))
            .distinct()
        )
    ).all()
    statuses = (
        await db.scalars(
            select(MondayEvent.new_value)
            .where(
                MondayEvent.board_id == board_id,
                MondayEvent.event_type == "status_changed",
                MondayEvent.new_value.isnot(None),
            )
            .distinct()
        )
    ).all()
    return BoardValues(groups=sorted(groups), statuses=sorted(statuses))
