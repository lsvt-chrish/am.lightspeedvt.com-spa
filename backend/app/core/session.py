"""Server-side session: signed session-id cookie and in-memory store."""
import secrets
from typing import Any

from itsdangerous import BadSignature, URLSafeTimedSerializer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import SECRET_KEY

# In-memory session store: session_id -> session dict
_sessions: dict[str, dict[str, Any]] = {}

COOKIE_NAME = "session_id"
COOKIE_MAX_AGE = 86400 * 7  # 7 days
SERIALIZER = URLSafeTimedSerializer(SECRET_KEY, salt="session-id")


def _get_or_create_session_id(request: Request) -> tuple[str, bool]:
    """Return (session_id, created). Verifies signature if cookie present."""
    raw = request.cookies.get(COOKIE_NAME)
    if raw:
        try:
            sid = SERIALIZER.loads(raw, max_age=COOKIE_MAX_AGE)
            if sid and sid in _sessions:
                return sid, False
        except BadSignature:
            pass
    return secrets.token_urlsafe(32), True


def _serialize_session_id(session_id: str) -> str:
    return SERIALIZER.dumps(session_id)


class SessionMiddleware(BaseHTTPMiddleware):
    """Attach request.state.session (dict) and persist session_id in a signed cookie."""

    async def dispatch(self, request: Request, call_next) -> Response:
        session_id, created = _get_or_create_session_id(request)
        if created:
            _sessions[session_id] = {}
        request.state.session = _sessions[session_id]

        response = await call_next(request)

        # Set or refresh cookie so client gets the session_id
        value = _serialize_session_id(session_id)
        response.set_cookie(
            COOKIE_NAME,
            value,
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
            path="/",
        )
        return response
