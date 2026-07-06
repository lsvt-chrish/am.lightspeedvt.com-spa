"""Attribute Pass-Through Link: redirect with LSVT user attributes as query params."""
import json
import logging
import re
import time
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.attribute_mapper import DEFAULT_ATTRIBUTES, apply_key_map
from app.core.config import APL_BLOCKED_ATTRIBUTES, APL_RATE_LIMIT
from app.lsvt_user import get_user_data
from app.redirect_validator import validate_redirect_url

logger = logging.getLogger(__name__)

router = APIRouter(tags=["apl"])

COOKIE_NAME = "LSVT_GUSERID"
# Rate limit: "100 per minute" -> (100, 60)
_rate_limit_parsed: tuple[int, int] | None = None
_rate_limit_timestamps: dict[str, list[float]] = {}


def _parse_rate_limit() -> tuple[int, int]:
    """Parse APL_RATE_LIMIT (e.g. '100 per minute') -> (max_requests, window_seconds)."""
    global _rate_limit_parsed
    if _rate_limit_parsed is not None:
        return _rate_limit_parsed
    m = re.match(r"(\d+)\s+per\s+(minute|min|hour|second|sec)", APL_RATE_LIMIT.lower())
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit in ("minute", "min"):
            _rate_limit_parsed = (n, 60)
        elif unit in ("hour",):
            _rate_limit_parsed = (n, 3600)
        else:
            _rate_limit_parsed = (n, 1)
    else:
        _rate_limit_parsed = (100, 60)
    return _rate_limit_parsed


def _check_rate_limit(client_ip: str) -> bool:
    """Return True if request is allowed, False if rate limited."""
    max_req, window = _parse_rate_limit()
    now = time.monotonic()
    if client_ip not in _rate_limit_timestamps:
        _rate_limit_timestamps[client_ip] = []
    timestamps = _rate_limit_timestamps[client_ip]
    # Prune older than window
    timestamps[:] = [t for t in timestamps if now - t < window]
    if len(timestamps) >= max_req:
        return False
    timestamps.append(now)
    return True


def _validate_user_id(user_id: str) -> bool:
    """Accept non-empty alphanumeric (and common separators) user IDs."""
    if not user_id or not user_id.strip():
        return False
    return bool(re.match(r"^[a-zA-Z0-9_\-]+$", user_id.strip()))


def _camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    parts = name.split("_")
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])


# Optional aliases for attribute names (requested name -> list of keys to try in order)
# LSVT API may use "login" or "displayName" instead of "username"
_ATTR_ALIASES: dict[str, list[str]] = {
    "userId": ["userId", "user_id", "id"],
    "username": ["username", "login", "displayName", "userName", "name"],
}

# For attributes that the API returns as objects (e.g. email = {address, messaging, ...}),
# which sub-key(s) to use to get a single string value (first found wins).
# accessLevel: use id (not name) so the redirect gets the level id.
_ATTR_OBJECT_KEYS: dict[str, list[str]] = {
    "email": ["address", "messaging", "email"],
    "username": ["username", "name", "userName"],
    "accessLevel": ["id", "name"],
}

# Attributes that come from nested keys (e.g. location.vendorID -> locationVendorId).
_ATTR_NESTED_PATHS: dict[str, list[str]] = {
    "locationVendorId": ["location", "vendorID"],
}


def _normalize_attr_value(value: object, attr_name: str) -> str | None:
    """
    Convert an attribute value to a single string for use in URL params.
    If the API returns an object (e.g. email = {address: 'x@y.com', ...}), extract a string.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value if value.strip() else None
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        keys = _ATTR_OBJECT_KEYS.get(attr_name, ["value", "name", "email", "address"])
        for k in keys:
            if k in value and value[k] is not None:
                s = _normalize_attr_value(value[k], attr_name)
                if s:
                    return s
        return None
    return str(value)


def _get_attr_value(user_data: dict, name: str) -> str | None:
    """Get attribute from user_data, trying exact key, aliases, nested paths, then snake/camel variants."""
    raw = None
    if name in _ATTR_ALIASES:
        for key in _ATTR_ALIASES[name]:
            if key in user_data and user_data[key] is not None:
                raw = user_data[key]
                break
    if raw is None and name in user_data and user_data[name] is not None:
        raw = user_data[name]
    if raw is None and name in _ATTR_NESTED_PATHS:
        path = _ATTR_NESTED_PATHS[name]
        obj = user_data
        for key in path:
            if not isinstance(obj, dict) or key not in obj:
                obj = None
                break
            obj = obj[key]
        if obj is not None:
            raw = obj
    if raw is None:
        alt = _camel_to_snake(name) if "_" not in name else _snake_to_camel(name)
        if alt in user_data and user_data[alt] is not None:
            raw = user_data[alt]
    if raw is None:
        return None
    return _normalize_attr_value(raw, name)


def _build_debug_response(
    *,
    cookie_present: bool,
    user_id: str | None,
    user_id_valid: bool,
    user_data_fetched: bool,
    user_data_keys: list[str],
    requested_attrs: list[str],
    attrs_found: dict[str, str],
    final_url: str | None,
    reason: str,
) -> JSONResponse:
    return JSONResponse(
        content={
            "cookie_present": cookie_present,
            "user_id": user_id,
            "user_id_valid": user_id_valid,
            "user_data_fetched": user_data_fetched,
            "user_data_keys": user_data_keys,
            "requested_attrs": requested_attrs,
            "attrs_found": attrs_found,
            "final_url": final_url,
            "reason": reason,
        }
    )


@router.get("/apl")
async def apl_redirect(request: Request):
    """
    Redirect to target URL with LSVT user attributes as query parameters.

    Query params: params (comma-separated attributes), redirect_url (required),
    optional key_map (URL-encoded JSON). Legacy: hook_url as alias for redirect_url.
    Add apl_debug=1 to get JSON diagnostics instead of redirecting.
    """
    debug = request.query_params.get("apl_debug", "").lower() in ("1", "true", "yes")

    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        if debug:
            return JSONResponse(
                status_code=429,
                content={
                    "reason": "rate_limited",
                    "cookie_present": bool(request.cookies.get(COOKIE_NAME)),
                    "user_id": request.cookies.get(COOKIE_NAME),
                    "user_id_valid": False,
                    "user_data_fetched": False,
                    "user_data_keys": [],
                    "requested_attrs": [],
                    "attrs_found": {},
                    "final_url": None,
                },
            )
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests"},
        )

    redirect_url = request.query_params.get("redirect_url") or request.query_params.get(
        "hook_url"
    )
    if not redirect_url:
        raise HTTPException(status_code=400, detail="redirect_url or hook_url required")

    valid, err_msg, err_type = validate_redirect_url(redirect_url)
    if not valid:
        if err_type == "forbidden":
            raise HTTPException(status_code=403, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)

    params_str = request.query_params.get("params", "")
    key_map_str = request.query_params.get("key_map", "")

    requested_attrs = [
        a.strip()
        for a in params_str.split(",")
        if a.strip()
    ]
    allowed = set(DEFAULT_ATTRIBUTES)
    blocked = set(APL_BLOCKED_ATTRIBUTES)
    requested_attrs = [
        a for a in requested_attrs
        if a in allowed and a not in blocked
    ]

    key_map: dict[str, str] | None = None
    if key_map_str:
        try:
            key_map = json.loads(key_map_str)
            if not isinstance(key_map, dict):
                key_map = None
        except json.JSONDecodeError:
            key_map = None

    user_id_raw = request.cookies.get(COOKIE_NAME)
    cookie_present = user_id_raw is not None
    user_id_valid = _validate_user_id(user_id_raw or "")

    if not user_id_valid:
        logger.warning("APL: missing or invalid %s cookie; redirecting without params", COOKIE_NAME)
        if debug:
            return _build_debug_response(
                cookie_present=cookie_present,
                user_id=user_id_raw,
                user_id_valid=False,
                user_data_fetched=False,
                user_data_keys=[],
                requested_attrs=requested_attrs,
                attrs_found={},
                final_url=redirect_url,
                reason="no_cookie",
            )
        return RedirectResponse(url=redirect_url, status_code=302)

    user_id = user_id_raw.strip()
    user_data = await get_user_data(user_id)
    if not user_data:
        logger.warning("APL: could not fetch user data for user_id=%s; redirecting without params", user_id)
        if debug:
            return _build_debug_response(
                cookie_present=True,
                user_id=user_id,
                user_id_valid=True,
                user_data_fetched=False,
                user_data_keys=[],
                requested_attrs=requested_attrs,
                attrs_found={},
                final_url=redirect_url,
                reason="user_data_fetch_failed",
            )
        return RedirectResponse(url=redirect_url, status_code=302)

    attrs: dict[str, str] = {}
    for name in requested_attrs:
        val = _get_attr_value(user_data, name)
        if val is not None:
            attrs[name] = val

    if not attrs:
        logger.warning(
            "APL: no requested attributes found in user data for user_id=%s (requested=%s, keys=%s); redirecting without params",
            user_id,
            requested_attrs,
            list(user_data.keys())[:20],
        )
        if debug:
            return _build_debug_response(
                cookie_present=True,
                user_id=user_id,
                user_id_valid=True,
                user_data_fetched=True,
                user_data_keys=list(user_data.keys())[:30],
                requested_attrs=requested_attrs,
                attrs_found={},
                final_url=redirect_url,
                reason="no_attrs_in_user_data",
            )
        return RedirectResponse(url=redirect_url, status_code=302)

    logger.info("APL: appending %s params for user_id=%s", list(attrs.keys()), user_id)

    mapped = apply_key_map(attrs, key_map)
    parsed = urlparse(redirect_url)
    query = parsed.query
    existing = {}
    if query:
        for k, v in parse_qs(query).items():
            existing[k] = v[0] if v else ""
    existing.update(mapped)
    new_query = urlencode(existing)
    new_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment,
    ))
    if debug:
        return _build_debug_response(
            cookie_present=True,
            user_id=user_id,
            user_id_valid=True,
            user_data_fetched=True,
            user_data_keys=list(user_data.keys())[:30],
            requested_attrs=requested_attrs,
            attrs_found=attrs,
            final_url=new_url,
            reason="ok",
        )
    return RedirectResponse(url=new_url, status_code=302)


@router.get("/test/set-cookie")
async def test_set_cookie(user_id: str = "3587995"):
    """
    For local/dev: set LSVT_GUSERID cookie and redirect to home.
    Disable or protect in production.
    """
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        COOKIE_NAME,
        user_id,
        max_age=86400,
        httponly=False,
        samesite="lax",
        path="/",
    )
    return response
