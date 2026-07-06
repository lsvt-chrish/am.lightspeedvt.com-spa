"""Training data CSV export: list users, locations, courses; export filtered training data as CSV."""
import asyncio
import csv
import io
import re
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.lightspeed_api import (
    get_certification_users_report,
    get_users_training_info,
    list_certifications,
    list_locations,
    list_users,
)
from app.lsvt_user import get_user_data

router = APIRouter(prefix="/training", tags=["training-export"])

# Rate limit: 10 per minute per client
_RATE_LIMIT = (10, 60)
_rate_timestamps: dict[str, list[float]] = {}

COLUMN_CONFIG: dict[str, dict[str, Any]] = {
    "id": {"label": "id", "default": True},
    "name": {"label": "name", "default": True},
    "email": {"label": "email", "default": True},
    "misc 2": {"label": "misc 2", "default": True},
    "courseCategory": {"label": "courseCategory", "default": True},
    "courseId": {"label": "courseId", "default": True},
    "courseName": {"label": "courseName", "default": True},
    "chapterId": {"label": "chapterId", "default": True},
    "chapterName": {"label": "chapterName", "default": True},
    "chapterAttemptDate": {"label": "chapterAttemptDate", "default": True},
    "chapterAttemptScore": {"label": "chapterAttemptScore", "default": True},
    "chapterAttemptStatus": {"label": "chapterAttemptStatus", "default": True},
    # Extra optional fields that may exist on user/course records:
    "username": {"label": "username", "default": False},
    "locationId": {"label": "locationId", "default": False},
    "locationName": {"label": "locationName", "default": False},
}

DEFAULT_HEADERS = [key for key, cfg in COLUMN_CONFIG.items() if cfg.get("default")]


def _has_credentials(session: dict) -> bool:
    return bool(session.get("api_key") and session.get("api_secret"))


def _check_rate_limit(client_ip: str) -> bool:
    max_req, window = _RATE_LIMIT
    now = time.monotonic()
    if client_ip not in _rate_timestamps:
        _rate_timestamps[client_ip] = []
    timestamps = _rate_timestamps[client_ip]
    timestamps[:] = [t for t in timestamps if now - t < window]
    if len(timestamps) >= max_req:
        return False
    timestamps.append(now)
    return True


def _safe_id(value: str) -> bool:
    return bool(value and re.match(r"^[a-zA-Z0-9_\-]+$", str(value).strip()))


def _parse_date(s: str | None) -> datetime | None:
    if not s or not str(s).strip():
        return None
    s = str(s).strip().replace("Z", "")
    if "." in s:
        s = s.split(".")[0]
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y",
        "%m/%d/%Y %H:%M:%S",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _user_is_active(record: dict[str, Any]) -> bool:
    """Best-effort active flag detection; defaults to active when unclear."""
    for key in ("isActive", "active", "status", "userStatus"):
        if key in record:
            val = record[key]
            if isinstance(val, bool):
                return val
            if isinstance(val, str):
                s = val.strip().lower()
                if s in ("active", "enabled", "true", "1", "yes"):
                    return True
                if s in ("inactive", "disabled", "false", "0", "no"):
                    return False
    return True


def build_training_csv(rows: list[dict[str, Any]], headers: list[str] | None = None) -> str:
    """Build CSV string. Columns order is headers (or DEFAULT_HEADERS)."""
    if headers is None or not headers:
        headers = DEFAULT_HEADERS
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for r in rows:
        writer.writerow([str(r.get(h, "") or "").replace("\n", " ").replace("\r", "") for h in headers])
    return buf.getvalue()


def _row_from_completion(
    user_id: str,
    name: str,
    email: str,
    misc2: str,
    course_id: str | int,
    course_name: str,
    course_category: str,
    chapter_attempt_date: str,
    chapter_attempt_score: str,
    chapter_attempt_status: str,
    chapter_id: str = "",
    chapter_name: str = "",
) -> dict[str, Any]:
    return {
        "id": user_id,
        "name": name,
        "email": email,
        "misc 2": misc2,
        "courseCategory": course_category,
        "courseId": course_id,
        "courseName": course_name,
        "chapterId": chapter_id,
        "chapterName": chapter_name,
        "chapterAttemptDate": chapter_attempt_date,
        "chapterAttemptScore": chapter_attempt_score,
        "chapterAttemptStatus": chapter_attempt_status,
    }


def _get_str(record: dict[str, Any], *keys: str, default: str = "") -> str:
    """First matching key from record; coerce to str."""
    for k in keys:
        if k in record and record[k] is not None:
            return str(record[k]).strip()
    return default


def _training_user_chapters_to_rows(
    user_obj: dict[str, Any],
    user_cache: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """
    Flatten one Training Info API user object into CSV rows (one per chapter).
    Expects user_obj with userId, firstName, lastName, username, email, userCourseChapters.
    Each chapter has courseCategory, courseId, courseName, chapterId, chapterName,
    chapterAttemptDate, chapterAttemptScore, chapterAttemptStatus.
    """
    uid = str(user_obj.get("userId") or user_obj.get("user_id") or "")
    name = (
        f"{user_obj.get('firstName', '')} {user_obj.get('lastName', '')}".strip()
        or _get_str(user_obj, "username", "displayName", "name")
    )
    email = _get_str(user_obj, "email", "userEmail")
    username = _get_str(user_obj, "username", "login")
    if uid and uid in user_cache:
        uc = user_cache[uid]
        if not name:
            name = uc.get("name", "")
        if not email:
            email = uc.get("email", "")
        misc2 = uc.get("misc2", "")
    else:
        misc2 = _get_str(user_obj, "misc2", "misc_2", "miscField2")

    chapters = user_obj.get("userCourseChapters") or user_obj.get("user_course_chapters") or []
    if not isinstance(chapters, list):
        chapters = []

    out: list[dict[str, Any]] = []
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        course_category = _get_str(ch, "courseCategory", "course_category")
        course_id = _get_str(ch, "courseId", "course_id")
        course_name = _get_str(ch, "courseName", "course_name")
        chapter_id = _get_str(ch, "chapterId", "chapter_id")
        chapter_name = _get_str(ch, "chapterName", "chapter_name")
        attempt_date = _get_str(ch, "chapterAttemptDate", "attemptDate", "date")
        score_val = ch.get("chapterAttemptScore") if isinstance(ch.get("chapterAttemptScore"), (int, float)) else ch.get("attemptScore")
        score = str(score_val) if score_val is not None else _get_str(ch, "chapterAttemptScore", "attemptScore")
        status = _get_str(ch, "chapterAttemptStatus", "attemptStatus", "completeStatus") or "Completed"

        row = _row_from_completion(
            user_id=uid,
            name=name or "",
            email=email or "",
            misc2=misc2 or "",
            course_id=course_id or "",
            course_name=course_name or "",
            course_category=course_category or "",
            chapter_attempt_date=attempt_date or "",
            chapter_attempt_score=score or "",
            chapter_attempt_status=status or "Completed",
            chapter_id=chapter_id,
            chapter_name=chapter_name,
        )
        row["username"] = username
        row["locationId"] = _get_str(user_obj, "locationId", "location_id")
        row["locationName"] = _get_str(user_obj, "locationName", "location_name")
        out.append(row)
    return out


def _training_response_to_rows(
    response: Any,
    user_cache: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """
    Normalize Training Info API response (list of users or single user) and flatten to
    one CSV row per userCourseChapters entry.
    """
    users: list[dict[str, Any]] = []
    if isinstance(response, list):
        users = [u for u in response if isinstance(u, dict)]
    elif isinstance(response, dict) and ("userId" in response or "userCourseChapters" in response):
        users = [response]

    rows: list[dict[str, Any]] = []
    for user_obj in users:
        rows.extend(_training_user_chapters_to_rows(user_obj, user_cache))
    return rows


@router.get("/users")
async def get_training_users(
    request: Request,
    page: int = 1,
    pageSize: int = 10,
    search: str | None = None,
    status: str = "active",
):
    """List users with server-side pagination. Requires session credentials."""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    session = request.state.session
    if not _has_credentials(session):
        raise HTTPException(status_code=401, detail="No credentials in session")
    api_key = session["api_key"]
    api_secret = session["api_secret"]

    all_users: list[dict[str, Any]] = []
    try:
        page_api = 1
        while True:
            batch = await list_users(api_key, api_secret, items_per_page=200, page=page_api)
            if not batch:
                break
            all_users.extend(batch)
            if len(batch) < 200:
                break
            page_api += 1
            await asyncio.sleep(0.2)
    except Exception:
        # Fallback: derive unique users from certification reports
        all_users = []
        certs = []
        p = 1
        while True:
            batch = await list_certifications(api_key, api_secret, items_per_page=200, page=p)
            if not batch:
                break
            certs.extend(batch)
            if len(batch) < 200:
                break
            p += 1
            await asyncio.sleep(0.2)
        seen: set[str] = set()
        for cert in certs:
            cid = cert.get("id")
            if cid is None:
                continue
            try:
                report = await get_certification_users_report(
                    api_key, api_secret, cid, items_per_page=200, page=1
                )
                for u in report:
                    uid = str(u.get("userId") or u.get("id") or "")
                    if uid and uid not in seen:
                        seen.add(uid)
                        name = f"{u.get('firstName', '')} {u.get('lastName', '')}".strip() or u.get("username", "")
                        all_users.append({
                            "id": uid,
                            "name": name,
                            "email": u.get("email", ""),
                            "locationId": u.get("locationId") or u.get("location_id"),
                            "locationName": u.get("locationName") or u.get("location_name") or "",
                        })
            except Exception:
                continue
            await asyncio.sleep(0.15)
        # Dedupe by id
        by_id: dict[str, dict] = {}
        for u in all_users:
            uid = str(u.get("id", ""))
            if uid and uid not in by_id:
                by_id[uid] = u
        all_users = list(by_id.values())

    if search and search.strip():
        q = search.strip().lower()
        all_users = [
            u for u in all_users
            if q in str(u.get("name", "")).lower()
            or q in str(u.get("email", "")).lower()
            or q in str(u.get("id", "")).lower()
        ]
    # Filter by active/inactive/all
    if status not in ("active", "inactive", "all"):
        raise HTTPException(status_code=400, detail="Invalid status; must be 'active', 'inactive', or 'all'")
    if status in ("active", "inactive"):
        want_active = status == "active"
        all_users = [u for u in all_users if _user_is_active(u) == want_active]
    total = len(all_users)
    start = (page - 1) * pageSize
    pageSize = max(1, min(100, pageSize))
    items = all_users[start : start + pageSize]
    return {"items": items, "total": total}


@router.get("/locations")
async def get_training_locations(
    request: Request,
    page: int = 1,
    pageSize: int = 10,
    search: str | None = None,
):
    """List locations with server-side pagination. Requires session credentials."""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    session = request.state.session
    if not _has_credentials(session):
        raise HTTPException(status_code=401, detail="No credentials in session")
    api_key = session["api_key"]
    api_secret = session["api_secret"]

    all_locations: list[dict[str, Any]] = []
    try:
        page_api = 1
        while True:
            batch = await list_locations(api_key, api_secret, items_per_page=200, page=page_api)
            if not batch:
                break
            all_locations.extend(batch)
            if len(batch) < 200:
                break
            page_api += 1
            await asyncio.sleep(0.2)
    except Exception:
        # Derive from certification user reports (unique locationId/locationName)
        by_id: dict[str | int, dict] = {}
        certs = []
        p = 1
        while True:
            batch = await list_certifications(api_key, api_secret, items_per_page=200, page=p)
            if not batch:
                break
            certs.extend(batch)
            if len(batch) < 200:
                break
            p += 1
            await asyncio.sleep(0.2)
        for cert in certs:
            cid = cert.get("id")
            if cid is None:
                continue
            try:
                report = await get_certification_users_report(
                    api_key, api_secret, cid, items_per_page=200, page=1
                )
                for u in report:
                    lid = u.get("locationId") or u.get("location_id")
                    if lid is not None and lid != "":
                        if lid not in by_id:
                            by_id[lid] = {
                                "id": lid,
                                "name": u.get("locationName") or u.get("location_name") or str(lid),
                            }
            except Exception:
                continue
            await asyncio.sleep(0.15)
        all_locations = list(by_id.values())

    if search and search.strip():
        q = search.strip().lower()
        all_locations = [
            loc for loc in all_locations
            if q in str(loc.get("name", "")).lower() or q in str(loc.get("id", "")).lower()
        ]
    total = len(all_locations)
    start = (page - 1) * pageSize
    pageSize = max(1, min(100, pageSize))
    items = all_locations[start : start + pageSize]
    return {"items": items, "total": total}


@router.get("/courses")
async def get_training_courses(request: Request):
    """List courses (certifications) for filter dropdown. Requires session credentials."""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    session = request.state.session
    if not _has_credentials(session):
        raise HTTPException(status_code=401, detail="No credentials in session")
    api_key = session["api_key"]
    api_secret = session["api_secret"]
    all_certs = []
    page = 1
    while True:
        batch = await list_certifications(api_key, api_secret, items_per_page=200, page=page)
        if not batch:
            break
        all_certs.extend(batch)
        if len(batch) < 200:
            break
        page += 1
        await asyncio.sleep(0.2)
    courses = [
        {
            "id": c.get("id"),
            "name": c.get("name", ""),
            "category": c.get("description") or c.get("descriptionSnippet") or "",
        }
        for c in all_certs
        if c.get("id") is not None
    ]
    return {"courses": courses}


@router.get("/export/columns")
async def get_export_columns():
    """Return available export columns with labels and defaults."""
    return {
        "columns": [
            {"key": key, "label": cfg.get("label", key), "default": bool(cfg.get("default", False))}
            for key, cfg in COLUMN_CONFIG.items()
        ]
    }


class ExportCsvBody(BaseModel):
    scope: str = Field(..., pattern="^(user|location|all)$")
    userIds: list[str] = Field(default_factory=list)
    locationIds: list[str] = Field(default_factory=list)
    courseIds: list[str] = Field(default_factory=list)
    startDate: str | None = None
    endDate: str | None = None
    userStatus: str = Field(default="active", pattern="^(active|inactive|all)$")
    columns: list[str] = Field(default_factory=list)


@router.post("/export/csv")
async def post_export_csv(request: Request, body: ExportCsvBody):
    """Generate training data CSV from selected users/locations and filters. Returns CSV file."""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    session = request.state.session
    if not _has_credentials(session):
        raise HTTPException(status_code=401, detail="No credentials in session")
    if body.scope == "user" and not body.userIds:
        raise HTTPException(status_code=400, detail="Select at least one user when scope is 'user'")
    if body.scope == "location" and not body.locationIds:
        raise HTTPException(status_code=400, detail="Select at least one location when scope is 'location'")

    api_key = session["api_key"]
    api_secret = session["api_secret"]
    start_dt = _parse_date(body.startDate)
    end_dt = _parse_date(body.endDate)
    # Normalize filter IDs to strings so comparisons work (client may send numbers)
    course_id_set = set(str(c) for c in body.courseIds) if body.courseIds else None
    user_ids_set = set(str(u) for u in body.userIds)
    location_ids_set = set(str(l) for l in body.locationIds)
    status_filter = body.userStatus
    # Validate and resolve requested columns (if any)
    requested_columns = [c for c in body.columns if c in COLUMN_CONFIG]
    headers = requested_columns or DEFAULT_HEADERS

    # Fetch all training data from Training Info API (bulk); no certification report fallback
    rows: list[dict[str, Any]] = []
    user_cache: dict[str, dict[str, str]] = {}
    _enrich_sem = asyncio.Semaphore(20)  # limit concurrent user-detail calls

    async def _enrich_user_cache(uid: str) -> None:
        if uid in user_cache:
            return
        async with _enrich_sem:
            if uid in user_cache:
                return
            user_cache[uid] = {"name": "", "email": "", "misc2": ""}
            try:
                details = await get_user_data(uid)
            except Exception:
                return
            if not isinstance(details, dict):
                return
            name = (
                f"{details.get('firstName', '')} {details.get('lastName', '')}".strip()
                or details.get("username") or details.get("displayName") or ""
            )
            email = details.get("email")
            if isinstance(email, dict):
                email = email.get("address") or email.get("messaging") or ""
            email = str(email or "")
            misc2_val = (
                details.get("misc2")
                or details.get("misc_2")
                or details.get("Misc2")
                or details.get("miscField2")
                or details.get("miscfield2")
            )
            misc2 = str(misc2_val) if misc2_val is not None else ""
            user_cache[uid] = {"name": name, "email": email, "misc2": misc2}

    # Paginate get_users_training_info to collect all users with userCourseChapters
    all_users: list[dict[str, Any]] = []
    page = 1
    try:
        while True:
            batch = await get_users_training_info(
                api_key,
                api_secret,
                start_date=body.startDate or None,
                end_date=body.endDate or None,
                items_per_page=200,
                page=page,
            )
            if not batch:
                break
            all_users.extend(batch)
            if len(batch) < 200:
                break
            page += 1
            await asyncio.sleep(0.08)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Training Info API unavailable: {e!s}",
        ) from e

    # Enrich cache with misc2 (and name/email if missing) for each unique user — concurrently
    seen_uids: list[str] = []
    seen_set: set[str] = set()
    for user_obj in all_users:
        uid = str(user_obj.get("userId") or user_obj.get("user_id") or "")
        if uid and uid not in seen_set:
            seen_set.add(uid)
            seen_uids.append(uid)
    await asyncio.gather(*(_enrich_user_cache(uid) for uid in seen_uids))

    # Flatten to one row per chapter
    for row in _training_response_to_rows(all_users, user_cache):
        # Scope filter (compare as strings)
        if body.scope == "user":
            if str(row.get("id", "") or "") not in user_ids_set:
                continue
        elif body.scope == "location":
            row_loc = str(row.get("locationId") or row.get("location_id") or "")
            if row_loc not in location_ids_set:
                continue
        if course_id_set is not None:
            row_course = str(row.get("courseId", "") or "")
            if row_course not in course_id_set:
                continue
        if start_dt or end_dt:
            attempt_date = row.get("chapterAttemptDate") or ""
            if attempt_date:
                dt = _parse_date(str(attempt_date))
                if dt:
                    if start_dt and dt < start_dt:
                        continue
                    if end_dt and dt > end_dt:
                        continue
        rows.append(row)

    csv_content = build_training_csv(rows, headers=headers)
    filename = f"training-export-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.csv"
    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
