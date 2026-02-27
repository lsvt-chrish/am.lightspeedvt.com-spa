"""LightSpeed VT REST API client for certifications (Basic auth, httpx)."""
import base64
import logging
from typing import Any

import httpx

from app.core.config import LIGHTSPEED_API_TIMEOUT

logger = logging.getLogger(__name__)

BASE_URL = "https://webservices.lightspeedvt.net/REST/V1"


def _basic_auth(api_key: str, api_secret: str) -> str:
    raw = f"{api_key}:{api_secret}"
    return base64.b64encode(raw.encode()).decode()


async def get_system_info(api_key: str, api_secret: str) -> dict[str, Any]:
    """
    Fetch system/account info from LightSpeed VT API.
    Returns dict with system_id and system_name (empty string if not present or on error).
    """
    out: dict[str, Any] = {"system_id": "", "system_name": ""}
    url = f"{BASE_URL}/account"
    headers = {"Authorization": f"Basic {_basic_auth(api_key, api_secret)}"}
    try:
        async with httpx.AsyncClient(timeout=LIGHTSPEED_API_TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("get_system_info failed: %s", e)
        return out
    if not isinstance(data, dict):
        return out
    # Unwrap nested response (e.g. {"account": {...}} or {"data": {...}})
    record = data
    for key in ("account", "data", "system", "result"):
        if key in data and isinstance(data[key], dict):
            record = data[key]
            break
    for id_key in ("systemId", "system_id", "accountId", "account_id", "id"):
        if id_key in record and record[id_key] is not None:
            out["system_id"] = str(record[id_key])
            break
    for name_key in ("systemName", "system_name", "accountName", "account_name", "name"):
        if name_key in record and record[name_key] is not None:
            out["system_name"] = str(record[name_key])
            break
    return out


def _normalize_list_response(data: Any) -> list[dict[str, Any]]:
    """Normalize API response to list of dicts (certifications or users)."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "certifications", "items", "users"):
            if key in data and isinstance(data[key], list):
                return data[key]
    return []


def _cert_id(entry: dict) -> str | int | None:
    """Extract certification ID from an entry."""
    for key in ("certificationId", "id", "certId"):
        if key in entry and entry[key] is not None:
            return entry[key]
    return None


def _cert_name(entry: dict) -> str:
    """Extract certification name from an entry."""
    for key in ("certificationName", "name", "title"):
        if key in entry and entry[key] is not None:
            return str(entry[key])
    return ""


async def list_certifications(
    api_key: str,
    api_secret: str,
    items_per_page: int = 200,
    page: int = 1,
) -> list[dict[str, Any]]:
    """
    Fetch certifications from LightSpeed VT API.
    Returns list of dicts with at least id and name (normalized keys).
    """
    url = f"{BASE_URL}/certifications"
    headers = {"Authorization": f"Basic {_basic_auth(api_key, api_secret)}"}
    params = {"itemsPerPage": items_per_page, "page": page}
    async with httpx.AsyncClient(timeout=LIGHTSPEED_API_TIMEOUT) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
    raw_list = _normalize_list_response(data)
    result = []
    for entry in raw_list:
        if isinstance(entry, dict):
            cid = _cert_id(entry)
            if cid is not None:
                result.append({
                    "id": cid,
                    "name": _cert_name(entry),
                    "description": entry.get("description") or entry.get("descriptionSnippet") or "",
                    **{k: v for k, v in entry.items() if k not in ("certificationId", "certId")},
                })
    return result


async def get_certification_users_report(
    api_key: str,
    api_secret: str,
    cert_id: str | int,
    items_per_page: int = 200,
    page: int = 1,
) -> list[dict[str, Any]]:
    """
    Fetch users report for a certification. Returns only rows with non-null completeDate.
    """
    url = f"{BASE_URL}/certifications/{cert_id}/users/report"
    headers = {"Authorization": f"Basic {_basic_auth(api_key, api_secret)}"}
    params = {"itemsPerPage": items_per_page, "page": page}
    async with httpx.AsyncClient(timeout=LIGHTSPEED_API_TIMEOUT) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
    raw_list = _normalize_list_response(data)
    result = []
    for row in raw_list:
        if not isinstance(row, dict):
            continue
        complete_date = row.get("completeDate")
        if complete_date is None or (isinstance(complete_date, str) and not complete_date.strip()):
            continue
        user_id = row.get("userId") or row.get("id")
        result.append({
            "userId": user_id,
            "firstName": row.get("firstName", ""),
            "lastName": row.get("lastName", ""),
            "username": row.get("username") or row.get("login") or row.get("displayName", ""),
            "email": _extract_email(row.get("email")),
            "completeDate": complete_date,
            **row,
        })
    return result


def _extract_email(email_val: Any) -> str:
    """Extract email string from value (may be dict with address/messaging)."""
    if email_val is None:
        return ""
    if isinstance(email_val, str):
        return email_val
    if isinstance(email_val, dict):
        return (
            email_val.get("address")
            or email_val.get("messaging")
            or email_val.get("email")
            or ""
        )
    return str(email_val)
