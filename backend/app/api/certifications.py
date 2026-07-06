"""Certifications API: list certifications, users report, certifications by user."""
import asyncio
import hashlib
import re
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import (
    CERTIFICATIONS_CACHE_TTL,
    CERTIFICATIONS_USER_CACHE_TTL,
)
from app.lightspeed_api import (
    get_certification_users_report,
    list_certifications,
)

router = APIRouter(prefix="/certifications", tags=["certifications"])

# Rate limit: 10 per minute per client
_CERT_RATE_LIMIT = (10, 60)
_cert_rate_timestamps: dict[str, list[float]] = {}


def _has_credentials(session: dict) -> bool:
    return bool(session.get("api_key") and session.get("api_secret"))


def _check_rate_limit(client_ip: str) -> bool:
    max_req, window = _CERT_RATE_LIMIT
    now = time.monotonic()
    if client_ip not in _cert_rate_timestamps:
        _cert_rate_timestamps[client_ip] = []
    timestamps = _cert_rate_timestamps[client_ip]
    timestamps[:] = [t for t in timestamps if now - t < window]
    if len(timestamps) >= max_req:
        return False
    timestamps.append(now)
    return True


def _safe_id(value: str) -> bool:
    """Allow alphanumeric, dash, underscore."""
    return bool(value and re.match(r"^[a-zA-Z0-9_\-]+$", value.strip()))


# In-memory caches: key -> (data, expiry)
_cert_list_cache: dict[str, tuple[list[dict], float]] = {}
_user_certs_cache: dict[str, tuple[list[dict], float]] = {}


def _cache_scope(api_key: str, api_secret: str) -> str:
    """
    Build a stable, non-reversible cache namespace for a credential pair.
    This prevents cross-account cache bleed when users switch credentials.
    """
    raw = f"{api_key}:{api_secret}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def clear_certifications_cache_for_credentials(api_key: str, api_secret: str) -> None:
    """
    Invalidate certification caches for one credential scope.
    Used when session credentials are replaced or cleared.
    """
    scope = _cache_scope(api_key, api_secret)
    prefix = f"{scope}:"
    list_keys = [k for k in _cert_list_cache if k.startswith(prefix)]
    user_keys = [k for k in _user_certs_cache if k.startswith(prefix)]
    for key in list_keys:
        _cert_list_cache.pop(key, None)
    for key in user_keys:
        _user_certs_cache.pop(key, None)


def _get_cached_list(scope: str) -> list[dict] | None:
    now = time.monotonic()
    key = f"{scope}:list"
    if key in _cert_list_cache:
        data, expiry = _cert_list_cache[key]
        if now < expiry:
            return data
        del _cert_list_cache[key]
    return None


def _set_cached_list(scope: str, data: list[dict]) -> None:
    _cert_list_cache[f"{scope}:list"] = (data, time.monotonic() + CERTIFICATIONS_CACHE_TTL)


def _get_cached_user_certs(scope: str, user_id: str) -> list[dict] | None:
    now = time.monotonic()
    key = f"{scope}:user_{user_id}"
    if key in _user_certs_cache:
        data, expiry = _user_certs_cache[key]
        if now < expiry:
            return data
        del _user_certs_cache[key]
    return None


def _set_cached_user_certs(scope: str, user_id: str, data: list[dict]) -> None:
    _user_certs_cache[f"{scope}:user_{user_id}"] = (
        data,
        time.monotonic() + CERTIFICATIONS_USER_CACHE_TTL,
    )


@router.get("")
async def get_certifications_list(request: Request):
    """List all certifications. Requires session credentials. Rate limited 10/min."""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    session = request.state.session
    if not _has_credentials(session):
        raise HTTPException(status_code=401, detail="No credentials in session")
    api_key = session["api_key"]
    api_secret = session["api_secret"]
    scope = _cache_scope(api_key, api_secret)
    cached = _get_cached_list(scope)
    if cached is not None:
        return {"certifications": cached}
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
    _set_cached_list(scope, all_certs)
    return {"certifications": all_certs}


@router.get("/by-user/{user_id}")
async def get_certifications_by_user(request: Request, user_id: str):
    """
    List certifications completed by the given user. Requires session credentials.
    Rate limited 10/min. May take a while; result is cached.
    """
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    if not _safe_id(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    session = request.state.session
    if not _has_credentials(session):
        raise HTTPException(status_code=401, detail="No credentials in session")
    api_key = session["api_key"]
    api_secret = session["api_secret"]
    scope = _cache_scope(api_key, api_secret)
    cached = _get_cached_user_certs(scope, user_id)
    if cached is not None:
        return {"certifications": cached, "user_id": user_id}
    certs_list = await list_certifications(api_key, api_secret, items_per_page=200, page=1)
    # Optional: paginate through all certs if more than 200
    results: list[dict[str, Any]] = []
    for cert in certs_list:
        cert_id = cert.get("id")
        if cert_id is None:
            continue
        try:
            users = await get_certification_users_report(
                api_key, api_secret, cert_id, items_per_page=200, page=1
            )
        except Exception:
            continue
        for u in users:
            uid = str(u.get("userId") or u.get("id") or "")
            if uid == user_id:
                results.append({
                    "cert_id": cert_id,
                    "cert_name": cert.get("name", ""),
                    "completeDate": u.get("completeDate"),
                    "userId": user_id,
                })
                break
        await asyncio.sleep(0.15)
    results.sort(key=lambda x: x.get("completeDate") or "", reverse=True)
    _set_cached_user_certs(scope, user_id, results)
    return {"certifications": results, "user_id": user_id}


@router.get("/{cert_id}/users/report")
async def get_certification_users(request: Request, cert_id: str):
    """Users who completed the given certification. Requires session credentials. Rate limited 10/min."""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    if not _safe_id(cert_id):
        raise HTTPException(status_code=400, detail="Invalid certification ID")
    session = request.state.session
    if not _has_credentials(session):
        raise HTTPException(status_code=401, detail="No credentials in session")
    api_key = session["api_key"]
    api_secret = session["api_secret"]
    all_users = []
    page = 1
    while True:
        try:
            batch = await get_certification_users_report(
                api_key, api_secret, cert_id, items_per_page=200, page=page
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"API error: {e!s}")
        if not batch:
            break
        all_users.extend(batch)
        if len(batch) < 200:
            break
        page += 1
        await asyncio.sleep(0.2)
    return {"users": all_users, "cert_id": cert_id}
