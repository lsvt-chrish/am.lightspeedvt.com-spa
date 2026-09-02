"""
AI Production dashboard endpoints (docs/monday-api-integration-plan.md).
Separate from monday_webhook.py/monday_boards.py, which handle *inbound*
webhook events -- this reads a snapshot populated by outbound Monday API
pulls (app.monday_production_refresh), on a 15-min scheduler plus an
on-demand "Refresh" button.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import MONDAY_ACCOUNT_SUBDOMAIN, MONDAY_PRODUCTION_BOARD_ID
from app.db.models import MondayProductionSnapshot
from app.db.session import get_db
from app.monday_production_client import MondayApiError
from app.monday_production_refresh import refresh_production_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(tags=["monday-production"])


def _monday_item_url(item_id: str) -> str:
    return f"https://{MONDAY_ACCOUNT_SUBDOMAIN}.monday.com/boards/{MONDAY_PRODUCTION_BOARD_ID}/pulses/{item_id}"


def _with_item_urls(detail: dict) -> dict:
    """Attach a monday_url to every item in each bucket's drill-down list, for the dashboard's link-back-to-board."""
    out = {}
    for bucket_key, bucket in detail.items():
        items = [{**item, "monday_url": _monday_item_url(item["item_id"])} for item in bucket["items"]]
        out[bucket_key] = {**bucket, "items": items}
    return out


@router.get("/production/dashboard")
async def get_production_dashboard(detail: bool = False, db: AsyncSession = Depends(get_db)):
    """
    Per docs/monday-api-integration-plan.md's "Recommended API Response".
    Returns the live summary; pass ?detail=true for the drill-down item lists
    behind each metric (each item includes a monday_url link back to it).
    """
    row = await db.scalar(
        select(MondayProductionSnapshot).where(MondayProductionSnapshot.board_id == MONDAY_PRODUCTION_BOARD_ID)
    )
    if not row:
        raise HTTPException(
            status_code=404,
            detail="No production snapshot yet -- trigger POST /api/monday/production/refresh first.",
        )

    body = {
        "generatedAt": row.fetched_at,
        "capacity": row.metrics["capacity"],
        "metrics": row.metrics["metrics"],
        "boardUrl": f"https://{MONDAY_ACCOUNT_SUBDOMAIN}.monday.com/boards/{MONDAY_PRODUCTION_BOARD_ID}",
    }
    if detail:
        body["detail"] = _with_item_urls(row.metrics["detail"])
    return body


@router.post("/monday/production/refresh")
async def refresh_production_dashboard(db: AsyncSession = Depends(get_db)):
    """
    On-demand pull, wired to the dashboard's Refresh button. Deliberately not
    admin-gated (unlike /monday/boards/*) -- it's a read-adjacent action any
    ops-dashboard viewer can trigger, and gating it behind the shared HTTP
    Basic admin credentials would mean a browser auth popup every time
    someone clicks Refresh.
    """
    try:
        row = await refresh_production_snapshot(db, MONDAY_PRODUCTION_BOARD_ID)
    except MondayApiError as e:
        logger.warning("monday production refresh failed: %s", e.message)
        raise HTTPException(status_code=502, detail=e.message)
    return {"fetched_at": row.fetched_at}
