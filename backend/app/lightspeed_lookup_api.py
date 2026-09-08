"""
Public (no-auth) LightSpeedVT user lookup, used to prefill the veteran's name
on pages embedded per-veteran (e.g. the VetComm buddy statement generator),
where there's no admin-entered API key/secret in session -- unlike
lightspeed_api.py's Basic-auth REST/V1 endpoints, used by the internal admin
tools (User Check, Certifications) that have session credentials.
"""
import logging
from typing import Any

import httpx

from app.core.config import LIGHTSPEED_API_TIMEOUT

logger = logging.getLogger(__name__)

BASE_URL = "https://cfws.lightspeedvt.com/rest/lsvtapi"


def _extract_name(data: Any) -> str:
    """Best-effort name extraction; response shape isn't formally documented."""
    if not isinstance(data, dict):
        return ""
    record = data
    for key in ("user", "data", "result"):
        if key in data and isinstance(data[key], dict):
            record = data[key]
            break
    first = record.get("firstName") or record.get("first_name") or ""
    last = record.get("lastName") or record.get("last_name") or ""
    full = f"{first} {last}".strip()
    if full:
        return full
    for key in ("name", "displayName", "fullName", "username"):
        if record.get(key):
            return str(record[key])
    return ""


async def get_user_name(user_id: str) -> str:
    """
    GET /users/{userId}. No auth required. Returns "" (never raises) on any
    failure -- this is a convenience prefill, not something that should ever
    block the page.
    """
    url = f"{BASE_URL}/users/{user_id}"
    try:
        async with httpx.AsyncClient(timeout=LIGHTSPEED_API_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("get_user_name failed for user_id=%s: %s", user_id, e)
        return ""
    return _extract_name(data)
