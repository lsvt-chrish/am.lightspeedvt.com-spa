"""LightSpeed VT REST API client for certifications (Basic auth, httpx)."""
import base64
import logging
from datetime import datetime
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
    """Normalize API response to list of dicts (certifications, users, training)."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in (
            "data", "certifications", "items", "users",
            "trainingInfo", "training", "results", "records", "report",
        ):
            if key in data and isinstance(data[key], list):
                return data[key]
        # Nested: e.g. {"data": {"trainingInfo": [...]}}
        inner = data.get("data") or data.get("result")
        if isinstance(inner, dict):
            for key in ("trainingInfo", "training", "items", "users", "results", "records"):
                if key in inner and isinstance(inner[key], list):
                    return inner[key]
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


async def list_users(
    api_key: str,
    api_secret: str,
    items_per_page: int = 200,
    page: int = 1,
) -> list[dict[str, Any]]:
    """
    Fetch users from LightSpeed VT API if the endpoint exists.
    Returns list of dicts with id, name, email, and optional location fields.
    Raises on 4xx/5xx; returns [] if endpoint is not available (caller may derive from reports).
    """
    url = f"{BASE_URL}/users"
    headers = {"Authorization": f"Basic {_basic_auth(api_key, api_secret)}"}
    params = {"itemsPerPage": items_per_page, "page": page}
    async with httpx.AsyncClient(timeout=LIGHTSPEED_API_TIMEOUT) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
    raw_list = _normalize_list_response(data)
    result = []
    for entry in raw_list:
        if not isinstance(entry, dict):
            continue
        uid = entry.get("userId") or entry.get("id")
        if uid is None:
            continue
        first = entry.get("firstName", "")
        last = entry.get("lastName", "")
        name = f"{first} {last}".strip() or entry.get("username") or entry.get("displayName") or ""
        result.append({
            "id": uid,
            "name": name,
            "email": _extract_email(entry.get("email")),
            "firstName": first,
            "lastName": last,
            "username": entry.get("username") or "",
            "locationId": entry.get("locationId") or entry.get("location_id"),
            "locationName": entry.get("locationName") or entry.get("location_name") or "",
            "nmlsId": entry.get("nmlsId") or entry.get("nmls_id") or "",
            **{k: v for k, v in entry.items() if k not in ("userId", "id")},
        })
    return result


def _unwrap_single_user(data: Any) -> dict[str, Any] | None:
    """Find a single-user object (one that has userId or userCourseChapters) inside common wrappers."""
    if not isinstance(data, dict):
        return None
    if "userId" in data or "userCourseChapters" in data:
        return data
    for key in ("data", "trainingInfo", "result", "user", "training"):
        inner = data.get(key)
        if isinstance(inner, dict) and ("userId" in inner or "userCourseChapters" in inner):
            return inner
    return None


def _to_lsvt_date(s: str | None) -> str | None:
    """
    Convert a date string to LSVT's expected MM-DD-YYYY format (dashes, US order).
    Accepts YYYY-MM-DD, MM-DD-YYYY, MM/DD/YYYY, or an ISO timestamp like
    YYYY-MM-DDTHH:MM:SS (with optional .ms / 'Z'). Returns None on failure.
    """
    if not s:
        return None
    s = str(s).strip()
    # Strip trailing Z and fractional seconds, then split off the time portion if present.
    s = s.rstrip("Z")
    if "." in s and "T" in s:
        s = s.split(".")[0]
    if "T" in s:
        s = s.split("T")[0]
    if " " in s:
        s = s.split(" ")[0]
    for fmt in ("%Y-%m-%d", "%m-%d-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%m-%d-%Y")
        except ValueError:
            continue
    return None


def _parse_user_training_response(
    data: Any,
) -> tuple[list[dict[str, Any]], int]:
    """Normalize the per-user training-info response and count chapters."""
    raw_list = _normalize_list_response(data)
    if not raw_list:
        single = _unwrap_single_user(data)
        if single is not None:
            raw_list = [single]
    users = [r for r in raw_list if isinstance(r, dict)]
    chapter_count = sum(
        len(u.get("userCourseChapters") or u.get("user_course_chapters") or [])
        for u in users
    )
    return users, chapter_count


async def get_user_training_info(
    api_key: str,
    api_secret: str,
    user_id: str | int,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch training data for a single user.
    GET /users/{userId}/trainingInfo.

    LSVT expects `startDate` / `endDate` query params formatted as MM-DD-YYYY (dashes).
    Without a date range LSVT defaults to the current month only.
    """
    url = f"{BASE_URL}/users/{user_id}/trainingInfo"
    headers = {"Authorization": f"Basic {_basic_auth(api_key, api_secret)}"}
    params: dict[str, str] = {}
    s = _to_lsvt_date(start_date)
    e = _to_lsvt_date(end_date)
    if s:
        params["startDate"] = s
    if e:
        params["endDate"] = e
    async with httpx.AsyncClient(timeout=LIGHTSPEED_API_TIMEOUT) as client:
        resp = await client.get(url, headers=headers, params=params or None)
        resp.raise_for_status()
        data = resp.json()
    users, chapter_count = _parse_user_training_response(data)
    logger.info(
        "get_user_training_info user=%s startDate=%s endDate=%s status=%s users=%d chapters=%d",
        user_id, s, e, resp.status_code, len(users), chapter_count,
    )
    if chapter_count == 0:
        try:
            snippet = (resp.text or "")[:400]
        except Exception:
            snippet = ""
        logger.warning(
            "get_user_training_info returned 0 chapters for user=%s; raw snippet=%r",
            user_id, snippet,
        )
    return users


async def get_users_training_info(
    api_key: str,
    api_secret: str,
    start_date: str | None = None,
    end_date: str | None = None,
    username: str | None = None,
    items_per_page: int = 200,
    page: int = 1,
) -> list[dict[str, Any]]:
    """
    Fetch training data for all users (or one user if username specified).
    GET /users/trainingInfo. Optional startDate/endDate (MM-DD-YYYY), username, pagination.
    Without dates LSVT returns the current month only.
    """
    url = f"{BASE_URL}/users/trainingInfo"
    headers = {"Authorization": f"Basic {_basic_auth(api_key, api_secret)}"}
    params: dict[str, str | int] = {"itemsPerPage": items_per_page, "page": page}
    s = _to_lsvt_date(start_date)
    e = _to_lsvt_date(end_date)
    if s:
        params["startDate"] = s
    if e:
        params["endDate"] = e
    if username:
        params["username"] = username
    async with httpx.AsyncClient(timeout=LIGHTSPEED_API_TIMEOUT) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
    raw_list = _normalize_list_response(data)
    return [r for r in raw_list if isinstance(r, dict)]


def _chapter_post_body(chapter: dict[str, Any]) -> dict[str, Any]:
    """
    Build a single chapter entry for POST /users/{id}/trainingInfo.

    Per LSVT's accepted shape, the body of that POST is a JSON array of these
    entries (see post_user_training_info). Each entry needs:
      - chapterId (int, globally unique; courseId is not part of the schema)
      - chapterAttemptDate (string, MM-DD-YYYY)
      - chapterAttemptScore (number)
      - chapterAttemptStatus (lowercase: "pass" / "fail" / etc.)
    """
    body: dict[str, Any] = {}
    chapter_id = chapter.get("chapterId") or chapter.get("chapter_id")
    if chapter_id is not None and str(chapter_id).strip() != "":
        try:
            body["chapterId"] = int(str(chapter_id).strip())
        except (TypeError, ValueError):
            body["chapterId"] = chapter_id
    formatted_date = _to_lsvt_date(
        chapter.get("chapterAttemptDate")
        or chapter.get("attemptDate")
        or chapter.get("date")
    )
    if formatted_date:
        body["chapterAttemptDate"] = formatted_date
    score = chapter.get("chapterAttemptScore")
    if score is None:
        score = chapter.get("attemptScore")
    if score is not None and str(score).strip() != "":
        try:
            body["chapterAttemptScore"] = int(str(score).strip())
        except (TypeError, ValueError):
            try:
                body["chapterAttemptScore"] = float(str(score).strip())
            except (TypeError, ValueError):
                body["chapterAttemptScore"] = score
    status = (
        chapter.get("chapterAttemptStatus")
        or chapter.get("attemptStatus")
        or chapter.get("completeStatus")
        or "pass"
    )
    body["chapterAttemptStatus"] = str(status).strip().lower()
    return body


async def post_user_training_info(
    api_key: str,
    api_secret: str,
    user_id: str | int,
    chapter: dict[str, Any],
) -> bool:
    """
    Write a chapter completion to a user's training info.
    POST /users/{userId}/trainingInfo with a JSON array body of chapter entries.
    Returns True on 2xx (LSVT returns a boolean).
    Raises httpx.HTTPStatusError on 4xx/5xx so the caller can surface the error.
    """
    url = f"{BASE_URL}/users/{user_id}/trainingInfo"
    headers = {
        "Authorization": f"Basic {_basic_auth(api_key, api_secret)}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = [_chapter_post_body(chapter)]
    async with httpx.AsyncClient(timeout=LIGHTSPEED_API_TIMEOUT) as client:
        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        if not resp.content:
            return True
        try:
            data = resp.json()
        except Exception:
            return True
    if isinstance(data, bool):
        return data
    if isinstance(data, dict):
        for key in ("success", "ok", "result"):
            if key in data and isinstance(data[key], bool):
                return data[key]
    return True


async def list_locations(
    api_key: str,
    api_secret: str,
    items_per_page: int = 200,
    page: int = 1,
) -> list[dict[str, Any]]:
    """
    Fetch locations from LightSpeed VT API if the endpoint exists.
    Returns list of dicts with id and name.
    Raises on 4xx/5xx; returns [] if endpoint is not available.
    """
    url = f"{BASE_URL}/locations"
    headers = {"Authorization": f"Basic {_basic_auth(api_key, api_secret)}"}
    params = {"itemsPerPage": items_per_page, "page": page}
    async with httpx.AsyncClient(timeout=LIGHTSPEED_API_TIMEOUT) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
    raw_list = _normalize_list_response(data)
    result = []
    for entry in raw_list:
        if not isinstance(entry, dict):
            continue
        lid = entry.get("locationId") or entry.get("id")
        if lid is None:
            continue
        result.append({
            "id": lid,
            "name": entry.get("locationName") or entry.get("name") or entry.get("location_name") or "",
            **{k: v for k, v in entry.items() if k not in ("locationId", "id")},
        })
    return result
