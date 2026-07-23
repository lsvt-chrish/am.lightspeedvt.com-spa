"""
One-off dev seeding script: adds ~10,000 synthetic monday_event rows spanning
the last year, against whatever monday_board rows already exist, so the ops
dashboard has data to render. Not wired into any app code path -- run
manually:

    uv run python -m app.scripts.seed_dashboard
"""
import asyncio
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import MondayBoard, MondayEvent
from app.db.session import AsyncSessionLocal

random.seed(42)

NOW = datetime.now(tz=timezone.utc)
YEAR_AGO = NOW - timedelta(days=365)

TARGET_NEW_EVENTS = 10_000


def random_time_after(start: datetime, max_days: int) -> datetime:
    delta_days = random.uniform(0, max_days)
    t = start + timedelta(days=delta_days)
    return min(t, NOW)


async def seed():
    async with AsyncSessionLocal() as db:
        boards = (await db.execute(select(MondayBoard))).scalars().all()
        if not boards:
            print("No monday_board rows found -- create at least one board before seeding events.")
            return

        # Use each board's own configured group->bucket mapping so seeded
        # events resolve buckets the same way real webhook events would.
        board_groups = []
        for b in boards:
            groups = (b.bucket_map or {}).get("groups") or {}
            if not groups:
                continue
            board_groups.append((b, groups))
        if not board_groups:
            print("No board has a non-empty bucket_map.groups -- nothing to seed against.")
            return

        starting_id = (
            await db.scalar(select(MondayEvent.item_id).order_by(MondayEvent.id.desc()).limit(1))
        )
        item_counter = int(starting_id) + 1 if starting_id and starting_id.isdigit() else 90000

        events: list[MondayEvent] = []

        while len(events) < TARGET_NEW_EVENTS:
            item_counter += 1
            board, groups = random.choice(board_groups)
            group_names = list(groups.keys())
            item_id = str(item_counter)
            item_name = f"{board.department} item #{item_counter}"
            created_at = YEAR_AGO + timedelta(
                days=random.uniform(0, 365), hours=random.uniform(0, 24)
            )
            if created_at > NOW:
                created_at = NOW

            first_group = random.choice(group_names)
            events.append(
                MondayEvent(
                    board_id=board.board_id,
                    item_id=item_id,
                    item_name=item_name,
                    event_type="created",
                    group_id=groups[first_group],
                    group_name=first_group,
                    column_id=None,
                    previous_value=None,
                    new_value=None,
                    department=board.department,
                    bucket=groups[first_group],
                    occurred_at=created_at,
                    raw_payload={"seed": True},
                )
            )

            # Roll how many further transitions this item goes through, moving
            # through the board's own group list (order as configured).
            remaining_groups = [g for g in group_names if g != first_group]
            random.shuffle(remaining_groups)
            roll = random.random()
            if roll < 0.35:
                n_transitions = 0
            elif roll < 0.65:
                n_transitions = 1
            elif roll < 0.9:
                n_transitions = 2
            else:
                n_transitions = len(remaining_groups)
            stages = remaining_groups[:n_transitions]

            last_time = created_at
            last_group = first_group
            for group_name in stages:
                last_time = random_time_after(last_time, max_days=30)
                events.append(
                    MondayEvent(
                        board_id=board.board_id,
                        item_id=item_id,
                        item_name=None,
                        event_type="status_changed",
                        group_id=groups[group_name],
                        group_name=group_name,
                        column_id="status",
                        previous_value=last_group,
                        new_value=group_name,
                        department=board.department,
                        bucket=groups[group_name],
                        occurred_at=last_time,
                        raw_payload={"seed": True},
                    )
                )
                last_group = group_name

        events = events[:TARGET_NEW_EVENTS]
        db.add_all(events)
        await db.commit()
        print(f"Seeded {len(events)} events across {item_counter} items "
              f"spanning {YEAR_AGO.date()} to {NOW.date()}.")


if __name__ == "__main__":
    asyncio.run(seed())
