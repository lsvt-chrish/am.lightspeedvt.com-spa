"""
Pulls the AI Production board from Monday.com, computes the dashboard
metrics, and upserts the single MondayProductionSnapshot row for that board.
Called both by the 15-minute APScheduler job (app.main) and the on-demand
POST /api/monday/production/refresh endpoint -- same function either way, so
the read endpoint always serves whichever pull happened most recently.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import MONDAY_PRODUCTION_CAPACITY_GOAL_HOURS
from app.db.models import MondayProductionSnapshot
from app.monday_production_client import fetch_board_items
from app.monday_production_metrics import compute_metrics

logger = logging.getLogger(__name__)


async def refresh_production_snapshot(db: AsyncSession, board_id: str) -> MondayProductionSnapshot:
    items = await fetch_board_items(board_id)
    metrics = compute_metrics(items, MONDAY_PRODUCTION_CAPACITY_GOAL_HOURS)
    fetched_at = datetime.now(timezone.utc)

    existing = await db.scalar(
        select(MondayProductionSnapshot).where(MondayProductionSnapshot.board_id == board_id)
    )
    if existing:
        existing.metrics = metrics
        existing.fetched_at = fetched_at
        row = existing
    else:
        row = MondayProductionSnapshot(board_id=board_id, metrics=metrics, fetched_at=fetched_at)
        db.add(row)

    await db.commit()
    await db.refresh(row)
    logger.info("monday production snapshot refreshed for board_id=%s (%d items)", board_id, len(items))
    return row
