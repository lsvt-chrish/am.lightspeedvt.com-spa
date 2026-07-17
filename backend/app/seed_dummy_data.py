"""
One-off dev helper: populate monday_board / monday_event with synthetic data so
the ops dashboard has something to render before real webhooks are connected.

Run inside the backend container: uv run python -m app.seed_dummy_data
Safe to re-run: clears existing monday_board/monday_event rows first.
"""
import asyncio
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.db.models import MondayBoard, MondayEvent
from app.db.session import AsyncSessionLocal

random.seed(42)

BUCKET_MAP = {
    "groups": {"Open Tasks": "open", "Awaiting Response": "pending", "Closed": "closed"},
    "statuses": {},
}

DEPARTMENTS = [
    {"board_id": "dummy-sa", "name": "Solutions Architect Tasks (dummy)", "department": "Solutions Architect", "base": 6, "trend": -0.3},
    {"board_id": "dummy-client-care", "name": "Client Care Tickets (dummy)", "department": "Client Care", "base": 18, "trend": 1.2},
    {"board_id": "dummy-config", "name": "Config Tickets (dummy)", "department": "Config", "base": 10, "trend": 0.8},
]

WEEKS = 8
GROUP_BUCKET = {"open": "Open Tasks", "pending": "Awaiting Response", "closed": "Closed"}


def _week_bounds(weeks_ago: int) -> tuple[datetime, datetime]:
    now = datetime.now(tz=timezone.utc)
    end = now - timedelta(days=7 * weeks_ago)
    start = end - timedelta(days=7)
    return start, end


def _random_time_in(start: datetime, end: datetime) -> datetime:
    delta = (end - start).total_seconds()
    return start + timedelta(seconds=random.uniform(0, delta))


async def seed_department(session, board_id: str, department: str, base: float, trend: float) -> None:
    item_counter = 0
    open_items: list[str] = []
    pending_items: list[str] = []

    for weeks_ago in range(WEEKS, 0, -1):
        week_index = WEEKS - weeks_ago  # 0 = oldest week
        start, end = _week_bounds(weeks_ago)

        new_count = max(1, round(base + trend * week_index + random.uniform(-2, 2)))
        for _ in range(new_count):
            item_counter += 1
            item_id = f"{board_id}-item-{item_counter}"
            occurred_at = _random_time_in(start, end)
            session.add(
                MondayEvent(
                    board_id=board_id,
                    item_id=item_id,
                    item_name=f"{department} ticket {item_counter}",
                    event_type="created",
                    group_id="topics",
                    group_name="Open Tasks",
                    column_id=None,
                    previous_value=None,
                    new_value=None,
                    department=department,
                    bucket="open",
                    occurred_at=occurred_at,
                    raw_payload={"seed": True},
                )
            )
            open_items.append(item_id)

        # Roughly a third of currently-open items move to pending this week.
        to_pending = random.sample(open_items, k=min(len(open_items), max(0, round(len(open_items) * 0.35))))
        for item_id in to_pending:
            open_items.remove(item_id)
            pending_items.append(item_id)
            occurred_at = _random_time_in(start, end)
            session.add(
                MondayEvent(
                    board_id=board_id,
                    item_id=item_id,
                    item_name=None,
                    event_type="status_changed",
                    group_id="awaiting_response",
                    group_name="Awaiting Response",
                    column_id="status",
                    previous_value="Unread",
                    new_value="Awaiting Response",
                    department=department,
                    bucket="pending",
                    occurred_at=occurred_at,
                    raw_payload={"seed": True},
                )
            )

        # Roughly half of currently-pending items close out this week.
        to_closed = random.sample(pending_items, k=min(len(pending_items), max(0, round(len(pending_items) * 0.5))))
        for item_id in to_closed:
            pending_items.remove(item_id)
            occurred_at = _random_time_in(start, end)
            session.add(
                MondayEvent(
                    board_id=board_id,
                    item_id=item_id,
                    item_name=None,
                    event_type="status_changed",
                    group_id="closed",
                    group_name="Closed",
                    column_id="status",
                    previous_value="Awaiting Response",
                    new_value="Done",
                    department=department,
                    bucket="closed",
                    occurred_at=occurred_at,
                    raw_payload={"seed": True},
                )
            )


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(MondayEvent))
        await session.execute(delete(MondayBoard))
        for dept in DEPARTMENTS:
            session.add(
                MondayBoard(
                    board_id=dept["board_id"],
                    name=dept["name"],
                    department=dept["department"],
                    bucket_map=BUCKET_MAP,
                )
            )
        await session.flush()
        for dept in DEPARTMENTS:
            await seed_department(session, dept["board_id"], dept["department"], dept["base"], dept["trend"])
        await session.commit()
    print(f"Seeded {len(DEPARTMENTS)} boards with {WEEKS} weeks of dummy events.")


if __name__ == "__main__":
    asyncio.run(main())
