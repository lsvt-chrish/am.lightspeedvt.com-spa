"""Scan interactive courseware JSON by URL and return path statistics."""
import json
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.path_analyzer import analyze, fetch_segment_durations

router = APIRouter(prefix="/scan", tags=["scan"])


class ScanPayload(BaseModel):
    json_url: str = Field(..., min_length=1)


@router.post("/paths")
async def scan_paths(payload: ScanPayload):
    """
    Fetch JSON from the given URL, analyze paths and segment durations,
    return total segment duration, total paths/segments, shortest/longest/average path.
    """
    url = payload.json_url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="URL must use http or https")
    if not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid URL")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch URL: HTTP {e.response.status_code}",
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {str(e)}") from e

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}") from e

    videos = data.get("videos") if isinstance(data, dict) else None
    durations_override = None
    if isinstance(videos, dict):
        async with httpx.AsyncClient(timeout=15.0) as client:
            durations_override = await fetch_segment_durations(videos, client)

    result = analyze(data, durations_override=durations_override)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
