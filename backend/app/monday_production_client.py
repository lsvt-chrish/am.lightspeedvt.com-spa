"""
Monday.com outbound GraphQL client for the AI Production dashboard
(docs/monday-api-integration-plan.md). This is the first outbound Monday
integration in this codebase -- the existing monday_* modules only handle
*inbound* webhook events. Follows the same httpx client-module convention as
vetcomm_api.py: module-level async functions, a per-call AsyncClient, a
custom error class.
"""
import logging
from typing import Any

import httpx

from app.core.config import MONDAY_API_TOKEN, MONDAY_API_URL

logger = logging.getLogger(__name__)

# Column ids on the AI Production board (18405675239), confirmed 2026-09-01.
# There is no "Last Updated" column -- Monday's Item type carries updated_at
# natively, so that's requested directly rather than via column_values.
PROJECT_STATUS_COLUMN_ID = "color_mm1t3z1j"
HOURS_COLUMN_ID = "numeric_mm57p53w"
GROUP_COLUMN_ID = "group_mm1th225"
ASSIGNED_PRODUCER_COLUMN_ID = "multiple_person_mm1tp0k0"

COLUMN_IDS = [PROJECT_STATUS_COLUMN_ID, HOURS_COLUMN_ID, ASSIGNED_PRODUCER_COLUMN_ID]

_ITEMS_PAGE_QUERY = """
query ($boardId: ID!, $columnIds: [String!], $limit: Int!) {
  boards(ids: [$boardId]) {
    items_page(limit: $limit) {
      cursor
      items {
        id
        name
        updated_at
        group { id title }
        column_values(ids: $columnIds) {
          id
          text
        }
      }
    }
  }
}
"""

_NEXT_ITEMS_PAGE_QUERY = """
query ($cursor: String!, $columnIds: [String!], $limit: Int!) {
  next_items_page(cursor: $cursor, limit: $limit) {
    cursor
    items {
      id
      name
      updated_at
      group { id title }
      column_values(ids: $columnIds) {
        id
        text
      }
    }
  }
}
"""

_RETRYABLE_ERROR_CODES = {"COMPLEXITY_BUDGET_EXHAUSTED", "RATE_LIMIT_EXCEEDED"}


class MondayApiError(Exception):
    """Raised when Monday's GraphQL API returns an error, or the HTTP call itself fails."""

    def __init__(self, message: str, status_code: int | None = None, errors: list[dict] | None = None):
        self.message = message
        self.status_code = status_code
        self.errors = errors or []
        super().__init__(message)

    @property
    def retryable(self) -> bool:
        return any((e.get("extensions") or {}).get("code") in _RETRYABLE_ERROR_CODES for e in self.errors)


def _item_from_raw(raw: dict) -> dict[str, Any]:
    column_values = {cv["id"]: cv.get("text") for cv in raw.get("column_values") or []}
    group = raw.get("group") or {}
    hours_text = column_values.get(HOURS_COLUMN_ID)
    try:
        hours = float(hours_text) if hours_text not in (None, "") else 0.0
    except ValueError:
        logger.warning("monday production item %s has non-numeric Hours value %r", raw.get("id"), hours_text)
        hours = 0.0
    return {
        "item_id": raw["id"],
        "name": raw.get("name"),
        "updated_at": raw.get("updated_at"),
        "group_id": group.get("id"),
        "group_name": group.get("title"),
        "status": column_values.get(PROJECT_STATUS_COLUMN_ID),
        "hours": hours,
        "assigned_producer": column_values.get(ASSIGNED_PRODUCER_COLUMN_ID),
    }


async def _graphql(query: str, variables: dict) -> dict:
    if not MONDAY_API_TOKEN:
        raise MondayApiError("Monday API token not configured (MONDAY_API_TOKEN)")

    headers = {
        "Authorization": MONDAY_API_TOKEN,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            MONDAY_API_URL, json={"query": query, "variables": variables}, headers=headers
        )

    try:
        data = resp.json()
    except Exception:
        data = {}

    if resp.status_code != 200:
        raise MondayApiError(f"Monday API returned HTTP {resp.status_code}", status_code=resp.status_code)

    if data.get("errors"):
        logger.warning("monday production API GraphQL errors: %s", data["errors"])
        raise MondayApiError("Monday API returned GraphQL errors", errors=data["errors"])

    return data["data"]


async def fetch_board_items(board_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """
    Fetch every item on the board with the columns needed for the production
    dashboard metrics, paginating via items_page/next_items_page cursors.
    """
    items: list[dict[str, Any]] = []

    data = await _graphql(
        _ITEMS_PAGE_QUERY, {"boardId": board_id, "columnIds": COLUMN_IDS, "limit": limit}
    )
    boards = data.get("boards") or []
    if not boards:
        raise MondayApiError(f"Board {board_id} not found or not accessible with this token")
    page = boards[0]["items_page"]
    items.extend(_item_from_raw(raw) for raw in page["items"])
    cursor = page.get("cursor")

    while cursor:
        data = await _graphql(
            _NEXT_ITEMS_PAGE_QUERY, {"cursor": cursor, "columnIds": COLUMN_IDS, "limit": limit}
        )
        page = data["next_items_page"]
        items.extend(_item_from_raw(raw) for raw in page["items"])
        cursor = page.get("cursor")

    return items
