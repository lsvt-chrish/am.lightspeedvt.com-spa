"""VetComm statement generation API client (Bearer auth + optional HMAC signing, httpx)."""
import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

from app.core.config import (
    VETCOMM_API_BASE_URL,
    VETCOMM_API_KEY,
    VETCOMM_API_TIMEOUT,
    VETCOMM_SHARED_SECRET,
)

logger = logging.getLogger(__name__)


class VetCommError(Exception):
    """Raised when VetComm returns a structured error response."""

    def __init__(self, code: str, message: str, status_code: int, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def _signature(body_bytes: bytes) -> str:
    digest = hmac.new(VETCOMM_SHARED_SECRET.encode(), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


async def generate_statement(
    request_id: str,
    condition: dict[str, Any],
    veteran_input: dict[str, Any],
    regeneration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Call POST /statements/generate. Returns the parsed success response.
    Raises VetCommError on any 4xx/5xx with a structured error body.
    """
    url = f"{VETCOMM_API_BASE_URL}/api/v1/statements/generate"
    body = {
        "request_id": request_id,
        "condition": condition,
        "veteran_input": veteran_input,
        "regeneration": regeneration,
    }
    body_bytes = json.dumps(body).encode()
    headers = {
        "Authorization": f"Bearer {VETCOMM_API_KEY}",
        "Content-Type": "application/json",
    }
    if VETCOMM_SHARED_SECRET:
        headers["X-VetComm-Signature"] = _signature(body_bytes)

    async with httpx.AsyncClient(timeout=VETCOMM_API_TIMEOUT) as client:
        resp = await client.post(url, content=body_bytes, headers=headers)

    try:
        data = resp.json()
    except Exception:
        data = {}

    if resp.status_code == 200 and isinstance(data, dict) and data.get("status") == "success":
        return data

    error = data.get("error") if isinstance(data, dict) else None
    code = (error or {}).get("code", "internal_error")
    message = (error or {}).get("message", "VetComm request failed.")
    logger.warning("vetcomm generate_statement failed status=%s code=%s", resp.status_code, code)
    raise VetCommError(code=code, message=message, status_code=resp.status_code, details=error or {})
