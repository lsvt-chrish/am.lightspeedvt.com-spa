"""CRUD for per-board department/bucket-mapping config used by the webhook ingester."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MondayBoard, MondayEvent
from app.db.session import get_db

router = APIRouter(prefix="/monday/boards", tags=["monday"])


class BucketMap(BaseModel):
    groups: dict[str, str] = {}
    statuses: dict[str, str] = {}


class BoardIn(BaseModel):
    board_id: str
    name: str
    department: str
    bucket_map: BucketMap = BucketMap()


class BoardOut(BoardIn):
    id: int


@router.get("", response_model=list[BoardOut])
async def list_boards(db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(MondayBoard).order_by(MondayBoard.department))).all()
    return rows


class UnmappedValue(BaseModel):
    kind: str  # "group" | "status"
    value: str
    count: int
    last_seen: datetime


@router.get("/{board_id}/unmapped", response_model=list[UnmappedValue])
async def list_unmapped(board_id: str, db: AsyncSession = Depends(get_db)):
    """
    Group names and status labels this board has actually produced (via logged
    events) that aren't yet classified in its bucket_map — i.e. things a user
    still needs to decide whether to fold into open/pending/closed or mark
    "excluded" so they stop showing up here.
    """
    board = await db.scalar(select(MondayBoard).where(MondayBoard.board_id == board_id))
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    known_groups = set((board.bucket_map or {}).get("groups") or {})
    known_statuses = set((board.bucket_map or {}).get("statuses") or {})

    out: list[UnmappedValue] = []

    group_rows = (
        await db.execute(
            select(MondayEvent.group_name, func.count(), func.max(MondayEvent.occurred_at))
            .where(MondayEvent.board_id == board_id, MondayEvent.group_name.isnot(None))
            .group_by(MondayEvent.group_name)
        )
    ).all()
    for group_name, count, last_seen in group_rows:
        if group_name not in known_groups:
            out.append(UnmappedValue(kind="group", value=group_name, count=count, last_seen=last_seen))

    status_rows = (
        await db.execute(
            select(MondayEvent.new_value, func.count(), func.max(MondayEvent.occurred_at))
            .where(
                MondayEvent.board_id == board_id,
                MondayEvent.event_type == "status_changed",
                MondayEvent.new_value.isnot(None),
            )
            .group_by(MondayEvent.new_value)
        )
    ).all()
    for status_label, count, last_seen in status_rows:
        if status_label not in known_statuses:
            out.append(UnmappedValue(kind="status", value=status_label, count=count, last_seen=last_seen))

    return sorted(out, key=lambda u: u.last_seen, reverse=True)


@router.put("/{board_id}", response_model=BoardOut)
async def upsert_board(board_id: str, body: BoardIn, db: AsyncSession = Depends(get_db)):
    if body.board_id != board_id:
        raise HTTPException(status_code=400, detail="board_id in body must match path")
    existing = await db.scalar(select(MondayBoard).where(MondayBoard.board_id == board_id))
    if existing:
        existing.name = body.name
        existing.department = body.department
        existing.bucket_map = body.bucket_map.model_dump()
        row = existing
    else:
        row = MondayBoard(
            board_id=board_id,
            name=body.name,
            department=body.department,
            bucket_map=body.bucket_map.model_dump(),
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/{board_id}", status_code=204)
async def delete_board(board_id: str, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(MondayBoard).where(MondayBoard.board_id == board_id))
    if not existing:
        raise HTTPException(status_code=404, detail="Board not found")
    await db.delete(existing)
    await db.commit()
