"""
Ingest Monday.com automation webhooks (item created / status changed) into the
append-only monday_event log.

Monday's "send webhook" automations don't sign payloads, so the webhook URL
configured in each board's automation must include ?token=<MONDAY_WEBHOOK_TOKEN>
as a shared secret. Requests without a matching token are rejected.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import MONDAY_WEBHOOK_TOKEN
from app.db.models import MondayBoard, MondayEvent
from app.db.session import get_db
from app.monday_events import parse_webhook_payload, resolve_bucket

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monday", tags=["monday"])


def _check_token(token: str | None) -> None:
    if not MONDAY_WEBHOOK_TOKEN:
        # No token configured: refuse to accept webhooks rather than silently
        # running open, since this endpoint has no other auth.
        raise HTTPException(status_code=503, detail="Monday webhook token not configured")
    if token != MONDAY_WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/webhook")
async def monday_webhook(request: Request, token: str | None = None, db: AsyncSession = Depends(get_db)):
    _check_token(token)
    payload = await request.json()

    # Monday.com's webhook registration handshake: echo the challenge back verbatim.
    if "challenge" in payload:
        return {"challenge": payload["challenge"]}

    parsed = parse_webhook_payload(payload)
    if parsed is None:
        logger.info("monday_webhook: ignoring unrecognized/unsupported event payload")
        return {"status": "ignored"}

    board = await db.scalar(select(MondayBoard).where(MondayBoard.board_id == parsed.board_id))
    if board is None:
        # First event ever seen for this board: auto-register it rather than
        # rejecting the webhook. Department is a placeholder ("Unassigned")
        # since we have no way to guess it -- someone needs to rename/assign
        # it properly via the admin page, but nothing is lost or 500s in the
        # meantime (and Monday.com won't be stuck retrying a failed delivery).
        board = MondayBoard(
            board_id=parsed.board_id,
            name=f"Unregistered board {parsed.board_id}",
            department="Unassigned",
            bucket_map={},
        )
        db.add(board)
        await db.flush()
        logger.warning(
            "monday_webhook: auto-registered previously-unknown board %s -- "
            "configure its name/department/bucket_map via the admin page",
            parsed.board_id,
        )

    department = board.department
    bucket = resolve_bucket(board.bucket_map, parsed.group_name, parsed.new_value)

    if bucket is None:
        # First time this board has produced this group/status: auto-register it as
        # "excluded" rather than leaving it unmapped forever. A human can promote it
        # to open/pending/closed later via the board admin page; this just guarantees
        # every group/status a board actually uses ends up explicitly classified.
        bucket_map = board.bucket_map or {}
        if parsed.group_name and parsed.group_name not in (bucket_map.get("groups") or {}):
            bucket_map.setdefault("groups", {})[parsed.group_name] = "excluded"
            logger.info(
                "monday_webhook: auto-registered new group %r on board %s as excluded",
                parsed.group_name, parsed.board_id,
            )
        elif (
            parsed.event_type == "status_changed"
            and parsed.new_value
            and parsed.new_value not in (bucket_map.get("statuses") or {})
        ):
            bucket_map.setdefault("statuses", {})[parsed.new_value] = "excluded"
            logger.info(
                "monday_webhook: auto-registered new status %r on board %s as excluded",
                parsed.new_value, parsed.board_id,
            )
        board.bucket_map = bucket_map
        flag_modified(board, "bucket_map")
        bucket = "excluded"

    db.add(
        MondayEvent(
            board_id=parsed.board_id,
            item_id=parsed.item_id,
            item_name=parsed.item_name,
            event_type=parsed.event_type,
            group_id=parsed.group_id,
            group_name=parsed.group_name,
            column_id=parsed.column_id,
            previous_value=parsed.previous_value,
            new_value=parsed.new_value,
            department=department,
            bucket=bucket,
            occurred_at=parsed.occurred_at,
            raw_payload=payload,
        )
    )
    await db.commit()
    return {"status": "ok"}
