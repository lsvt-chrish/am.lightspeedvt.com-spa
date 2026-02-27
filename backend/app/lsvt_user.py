"""Fetch LSVT user data by ID with optional in-memory cache."""
import logging
import time
from typing import Any

import httpx

from app.core.config import APL_USER_CACHE_TTL

logger = logging.getLogger(__name__)

LSVT_USERS_URL = "https://cfws.lightspeedvt.com/rest/lsvtapi/users/{user_id}"

# In-memory cache: user_id -> (data dict, expiry timestamp)
_user_cache: dict[str, tuple[dict[str, Any], float]] = {}


def _cache_get(user_id: str) -> dict[str, Any] | None:
    now = time.monotonic()
    if user_id in _user_cache:
        data, expiry = _user_cache[user_id]
        if now < expiry:
            return data
        del _user_cache[user_id]
    return None


def _cache_set(user_id: str, data: dict[str, Any]) -> None:
    _user_cache[user_id] = (data, time.monotonic() + APL_USER_CACHE_TTL)


async def get_user_data(user_id: str) -> dict[str, Any] | None:
    """
    Fetch user attributes from LSVT API by user ID.

    Uses in-memory cache with TTL from config. On API error or timeout,
    returns None (caller should redirect without attributes).
    """
    cached = _cache_get(user_id)
    if cached is not None:
        return cached

    url = LSVT_USERS_URL.format(user_id=user_id)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                logger.warning("LSVT user response was not a dict: %s", type(data))
                return None
            # Unwrap if API returns nested user (e.g. {"user": {...}} or {"data": {...}})
            record = data
            for key in ("user", "data", "result", "User", "Data"):
                if key in data and isinstance(data[key], dict):
                    record = data[key]
                    break
            _cache_set(user_id, record)
            return record
    except httpx.HTTPStatusError as e:
        logger.warning("LSVT user API error for user_id=%s: %s", user_id, e)
        return None
    except httpx.RequestError as e:
        logger.warning("LSVT user request error for user_id=%s: %s", user_id, e)
        return None
    except Exception as e:
        logger.exception("Unexpected error fetching LSVT user %s: %s", user_id, e)
        return None
