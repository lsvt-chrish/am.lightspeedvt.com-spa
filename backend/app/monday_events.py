"""
Parsing + bucket resolution for Monday.com automation webhook payloads.

Monday.com's "send webhook" automation recipes POST an envelope shaped like
{"event": {...}}. The two events this integration cares about:

  - item created:        event.type contains "create" (e.g. "create_pulse")
  - status column change: event.type contains "update_column_value", with the
    changed column's new/previous value under event.value / event.previousValue
    as {"label": {"text": "..."}}.

Field names/shape are not formally versioned by Monday.com, so parsing here is
deliberately defensive (falls back across a few known key variants) rather
than assuming one exact schema.
"""
from datetime import datetime, timezone
from typing import Any


class ParsedMondayEvent:
    def __init__(
        self,
        board_id: str,
        item_id: str,
        item_name: str | None,
        event_type: str,
        group_id: str | None,
        group_name: str | None,
        column_id: str | None,
        previous_value: str | None,
        new_value: str | None,
        occurred_at: datetime,
    ) -> None:
        self.board_id = board_id
        self.item_id = item_id
        self.item_name = item_name
        self.event_type = event_type
        self.group_id = group_id
        self.group_name = group_name
        self.column_id = column_id
        self.previous_value = previous_value
        self.new_value = new_value
        self.occurred_at = occurred_at


def _label_text(value: Any) -> str | None:
    """Extract the human-readable label from a Monday status-column value."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        label = value.get("label")
        if isinstance(label, dict):
            return label.get("text")
        if isinstance(label, str):
            return label
        if "text" in value:
            return value.get("text")
    return None


def _trigger_time(event: dict) -> datetime:
    raw = event.get("triggerTime") or event.get("changedAt")
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw, tz=timezone.utc)
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(tz=timezone.utc)


def parse_webhook_payload(payload: dict) -> ParsedMondayEvent | None:
    """Return a ParsedMondayEvent for a supported event type, or None to ignore it."""
    event = payload.get("event")
    if not isinstance(event, dict):
        return None

    raw_type = str(event.get("type") or "")
    board_id = event.get("boardId") or event.get("board_id")
    item_id = event.get("pulseId") or event.get("itemId") or event.get("item_id")
    if board_id is None or item_id is None:
        return None

    if "create" in raw_type:
        event_type = "created"
        previous_value = None
        new_value = None
        column_id = None
    elif "update_column_value" in raw_type or "change_status" in raw_type:
        event_type = "status_changed"
        column_id = event.get("columnId") or event.get("column_id")
        previous_value = _label_text(event.get("previousValue"))
        new_value = _label_text(event.get("value"))
    else:
        return None

    return ParsedMondayEvent(
        board_id=str(board_id),
        item_id=str(item_id),
        item_name=event.get("pulseName") or event.get("itemName"),
        event_type=event_type,
        group_id=event.get("groupId"),
        group_name=event.get("groupName") or event.get("group_name"),
        column_id=column_id,
        previous_value=previous_value,
        new_value=new_value,
        occurred_at=_trigger_time(event),
    )


def resolve_bucket(bucket_map: dict, group_name: str | None, status_label: str | None) -> str | None:
    """
    Resolve a canonical bucket (open/new/pending/closed) for an event, given the
    owning board's bucket_map. Group-name mapping takes priority (matches how
    the SA Tasks board buckets by group), falling back to a status-label
    mapping for boards that bucket by status column instead.
    """
    groups = bucket_map.get("groups") or {}
    if group_name and group_name in groups:
        return groups[group_name]
    statuses = bucket_map.get("statuses") or {}
    if status_label and status_label in statuses:
        return statuses[status_label]
    return None
