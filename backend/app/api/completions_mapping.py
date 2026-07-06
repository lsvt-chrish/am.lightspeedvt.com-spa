"""Map chapter-level course completions from a source LSVT user to a destination user."""
import asyncio
import logging
import re
import time
from datetime import datetime
from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.lightspeed_api import (
    get_user_training_info,
    post_user_training_info,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/completions-mapping", tags=["completions-mapping"])

_RATE_LIMIT = (10, 60)
_rate_timestamps: dict[str, list[float]] = {}

_WRITE_CONCURRENCY = 5
_WRITE_DELAY_SECONDS = 0.1


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


def _validate_date(value: str | None, field: str) -> str | None:
    """Accept YYYY-MM-DD or full ISO; return normalized YYYY-MM-DD. Raise 400 on bad input."""
    if value is None or str(value).strip() == "":
        return None
    s = str(value).strip().replace("Z", "")
    if "." in s:
        s = s.split(".")[0]
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail=f"Invalid {field}; expected YYYY-MM-DD")


def _is_pass(status: Any) -> bool:
    if not status:
        return False
    return str(status).strip().lower() in ("pass", "passed", "complete", "completed", "success")


def _attempt_rank(ch: dict[str, Any]) -> tuple[int, str]:
    """
    Higher tuple sorts as 'better' attempt for the same (courseId, chapterId).
    Prefer pass over fail; within the same pass/fail bucket prefer the latest date.
    """
    return (
        1 if _is_pass(ch.get("chapterAttemptStatus")) else 0,
        str(ch.get("chapterAttemptDate") or ""),
    )


def _flatten_chapters(user_objs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Flatten the trainingInfo response (list of user objects) to a list of chapter dicts,
    keeping only the best attempt per (courseId, chapterId): pass > fail, then latest date.
    """
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for user_obj in user_objs:
        if not isinstance(user_obj, dict):
            continue
        chapters = user_obj.get("userCourseChapters") or user_obj.get("user_course_chapters") or []
        if not isinstance(chapters, list):
            continue
        for ch in chapters:
            if not isinstance(ch, dict):
                continue
            course_id = ch.get("courseId") or ch.get("course_id")
            chapter_id = ch.get("chapterId") or ch.get("chapter_id")
            if course_id is None or chapter_id is None:
                continue
            normalized = {
                "courseId": course_id,
                "courseName": ch.get("courseName") or ch.get("course_name") or "",
                "courseCategory": ch.get("courseCategory") or ch.get("course_category") or "",
                "chapterId": chapter_id,
                "chapterName": ch.get("chapterName") or ch.get("chapter_name") or "",
                "chapterAttemptDate": ch.get("chapterAttemptDate")
                or ch.get("attemptDate")
                or ch.get("date")
                or "",
                "chapterAttemptScore": ch.get("chapterAttemptScore")
                if ch.get("chapterAttemptScore") is not None
                else ch.get("attemptScore", ""),
                "chapterAttemptStatus": ch.get("chapterAttemptStatus")
                or ch.get("attemptStatus")
                or ch.get("completeStatus")
                or "",
            }
            key = (str(course_id), str(chapter_id))
            existing = best.get(key)
            if existing is None or _attempt_rank(normalized) > _attempt_rank(existing):
                best[key] = normalized
    return list(best.values())


def _chapter_key(chapter: dict[str, Any]) -> tuple[str, str]:
    return (str(chapter.get("courseId") or ""), str(chapter.get("chapterId") or ""))


@router.get("/preview")
async def preview_mapping(
    request: Request,
    source_user_id: str,
    destination_user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """
    Compare chapter completions between source and destination users.
    Returns each source chapter classified as 'new' or 'existing' (already on destination).

    Optional `start_date` / `end_date` (YYYY-MM-DD) bound the window queried from
    LSVT's GET /users/{userId}/trainingInfo. Without them LSVT defaults to the
    current month, so older completions will not appear.
    """
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    if not _safe_id(source_user_id):
        raise HTTPException(status_code=400, detail="Invalid source user ID")
    if not _safe_id(destination_user_id):
        raise HTTPException(status_code=400, detail="Invalid destination user ID")
    if str(source_user_id).strip() == str(destination_user_id).strip():
        raise HTTPException(
            status_code=400, detail="Source and destination must be different users"
        )
    start_norm = _validate_date(start_date, "start_date")
    end_norm = _validate_date(end_date, "end_date")
    if start_norm and end_norm and start_norm > end_norm:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    session = request.state.session
    if not _has_credentials(session):
        raise HTTPException(status_code=401, detail="No credentials in session")
    api_key = session["api_key"]
    api_secret = session["api_secret"]

    try:
        source_resp, dest_resp = await asyncio.gather(
            get_user_training_info(
                api_key, api_secret, source_user_id, start_norm, end_norm
            ),
            get_user_training_info(
                api_key, api_secret, destination_user_id, start_norm, end_norm
            ),
        )
    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response is not None else 502
        raise HTTPException(
            status_code=502 if status >= 500 else status,
            detail=f"LightSpeed VT API error: {e!s}",
        ) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LightSpeed VT API error: {e!s}") from e

    source_chapters = _flatten_chapters(source_resp)
    dest_chapters = _flatten_chapters(dest_resp)
    logger.info(
        "preview source=%s dest=%s window=%s..%s source_users=%d source_chapters=%d dest_users=%d dest_chapters=%d",
        source_user_id, destination_user_id, start_norm, end_norm,
        len(source_resp), len(source_chapters), len(dest_resp), len(dest_chapters),
    )
    dest_by_key: dict[tuple[str, str], dict[str, Any]] = {
        _chapter_key(ch): ch for ch in dest_chapters
    }

    chapters: list[dict[str, Any]] = []
    seen_source_keys: set[tuple[str, str]] = set()
    new_count = 0
    existing_count = 0
    for ch in source_chapters:
        key = _chapter_key(ch)
        if key in seen_source_keys:
            continue
        seen_source_keys.add(key)
        existing = dest_by_key.get(key)
        if existing is None:
            new_count += 1
            chapters.append({**ch, "status": "new", "destination_existing": None})
        else:
            existing_count += 1
            chapters.append({**ch, "status": "existing", "destination_existing": existing})

    return {
        "source_user_id": source_user_id,
        "destination_user_id": destination_user_id,
        "start_date": start_norm,
        "end_date": end_norm,
        "chapters": chapters,
        "summary": {
            "source_total": len(source_chapters),
            "destination_total": len(dest_chapters),
            "new": new_count,
            "existing": existing_count,
        },
    }


class ChapterRef(BaseModel):
    courseId: str | int
    chapterId: str | int
    chapterAttemptDate: str | None = None
    chapterAttemptScore: str | int | float | None = None
    chapterAttemptStatus: str | None = None


class ApplyBody(BaseModel):
    source_user_id: str = Field(..., min_length=1)
    destination_user_id: str = Field(..., min_length=1)
    conflict_mode: Literal["skip", "overwrite"] = "skip"
    chapters: list[ChapterRef] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None


@router.post("/apply")
async def apply_mapping(request: Request, body: ApplyBody):
    """
    Write the selected chapter completions onto the destination user.
    Enforces conflict_mode server-side by re-fetching destination's existing chapters.
    """
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    if not _safe_id(body.source_user_id):
        raise HTTPException(status_code=400, detail="Invalid source user ID")
    if not _safe_id(body.destination_user_id):
        raise HTTPException(status_code=400, detail="Invalid destination user ID")
    if body.source_user_id.strip() == body.destination_user_id.strip():
        raise HTTPException(
            status_code=400, detail="Source and destination must be different users"
        )
    if not body.chapters:
        raise HTTPException(status_code=400, detail="No chapters provided")
    start_norm = _validate_date(body.start_date, "start_date")
    end_norm = _validate_date(body.end_date, "end_date")
    if start_norm and end_norm and start_norm > end_norm:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    session = request.state.session
    if not _has_credentials(session):
        raise HTTPException(status_code=401, detail="No credentials in session")
    api_key = session["api_key"]
    api_secret = session["api_secret"]

    try:
        dest_resp = await get_user_training_info(
            api_key, api_secret, body.destination_user_id, start_norm, end_norm
        )
    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response is not None else 502
        raise HTTPException(
            status_code=502 if status >= 500 else status,
            detail=f"LightSpeed VT API error: {e!s}",
        ) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LightSpeed VT API error: {e!s}") from e

    dest_chapters = _flatten_chapters(dest_resp)
    dest_keys = {_chapter_key(ch) for ch in dest_chapters}

    sem = asyncio.Semaphore(_WRITE_CONCURRENCY)

    async def _write_one(ref: ChapterRef) -> dict[str, Any]:
        key = (str(ref.courseId), str(ref.chapterId))
        already = key in dest_keys
        if already and body.conflict_mode == "skip":
            return {
                "courseId": ref.courseId,
                "chapterId": ref.chapterId,
                "ok": True,
                "skipped": True,
                "error": None,
            }
        payload: dict[str, Any] = {
            "courseId": ref.courseId,
            "chapterId": ref.chapterId,
        }
        if ref.chapterAttemptDate:
            payload["chapterAttemptDate"] = ref.chapterAttemptDate
        if ref.chapterAttemptScore is not None and str(ref.chapterAttemptScore).strip() != "":
            payload["chapterAttemptScore"] = ref.chapterAttemptScore
        payload["chapterAttemptStatus"] = ref.chapterAttemptStatus or "Completed"

        async with sem:
            try:
                ok = await post_user_training_info(
                    api_key, api_secret, body.destination_user_id, payload
                )
                await asyncio.sleep(_WRITE_DELAY_SECONDS)
                return {
                    "courseId": ref.courseId,
                    "chapterId": ref.chapterId,
                    "ok": bool(ok),
                    "skipped": False,
                    "error": None if ok else "API returned a non-success response",
                }
            except httpx.HTTPStatusError as e:
                status = e.response.status_code if e.response is not None else "?"
                detail = ""
                try:
                    detail = e.response.text[:200] if e.response is not None else ""
                except Exception:
                    detail = ""
                logger.warning(
                    "post_user_training_info failed for user=%s chapter=%s: %s",
                    body.destination_user_id, ref.chapterId, e,
                )
                return {
                    "courseId": ref.courseId,
                    "chapterId": ref.chapterId,
                    "ok": False,
                    "skipped": False,
                    "error": f"HTTP {status}: {detail}".strip(),
                }
            except Exception as e:
                logger.exception(
                    "Unexpected error posting chapter for user=%s chapter=%s",
                    body.destination_user_id, ref.chapterId,
                )
                return {
                    "courseId": ref.courseId,
                    "chapterId": ref.chapterId,
                    "ok": False,
                    "skipped": False,
                    "error": str(e),
                }

    results = await asyncio.gather(*(_write_one(c) for c in body.chapters))

    created = sum(1 for r in results if r["ok"] and not r["skipped"])
    skipped = sum(1 for r in results if r["skipped"])
    failed = sum(1 for r in results if not r["ok"])
    return {
        "source_user_id": body.source_user_id,
        "destination_user_id": body.destination_user_id,
        "conflict_mode": body.conflict_mode,
        "start_date": start_norm,
        "end_date": end_norm,
        "results": results,
        "created": created,
        "skipped": skipped,
        "failed": failed,
    }
