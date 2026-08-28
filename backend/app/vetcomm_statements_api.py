"""
VetComm statements ingest/read API client (httpx). Separate service from
vetcomm_api.py's statement *generation* API -- this one stores/retrieves
saved statements. See the artifact scanned for this feature's spec:
- POST /v1/statements  (ingest token, Idempotency-Key required)
- GET  /v1/statements/{user_id}  (read token)
- GET  /health  (no token)

Errors: {"error": {"code", "message", "details": {"issues": [...]}}}
Status codes: 400 bad_request/invalid_json, 401 unauthorized, 404 not_found,
405 method_not_allowed, 413 payload_too_large, 422 validation_failed,
500 internal_error.
"""
import json
import logging
from typing import Any

import httpx

from app.core.config import (
    VETCOMM_INGEST_TOKEN,
    VETCOMM_READ_TOKEN,
    VETCOMM_STATEMENTS_API_BASE_URL,
    VETCOMM_STATEMENTS_API_TIMEOUT,
)

logger = logging.getLogger(__name__)

# Server documents a 512 KB request body cap; enforce client-side too so we
# fail fast with a clear error instead of waiting on a 413 round-trip.
MAX_PAYLOAD_BYTES = 512 * 1024


class VetCommStatementsError(Exception):
    """Raised when the statements API returns a structured error response."""

    def __init__(self, code: str, message: str, status_code: int, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


async def submit_statement(
    user_id: str,
    statement: str,
    idempotency_key: str,
    generated_at: str,
    condition_name: str,
    condition_category: str,
    attempt_number: int,
    character_count: int,
    request: dict[str, Any],
) -> dict[str, Any]:
    """
    Call POST /v1/statements. Returns the parsed stored record on success.
    Raises VetCommStatementsError on any 4xx/5xx with a structured error body.
    """
    url = f"{VETCOMM_STATEMENTS_API_BASE_URL}/v1/statements"
    body = {
        "user_id": user_id,
        "statement": statement,
        "generated_at": generated_at,
        "condition_name": condition_name,
        "condition_category": condition_category,
        "attempt_number": attempt_number,
        "character_count": character_count,
        # Everything beyond the required user_id/statement fields is stored
        # as-is in the record's `payload` field -- keep the exact request
        # that produced this statement so the full interaction is retrievable.
        "request": request,
    }
    body_bytes = json.dumps(body).encode()

    if len(body_bytes) > MAX_PAYLOAD_BYTES:
        raise VetCommStatementsError(
            code="payload_too_large",
            message=f"Save payload of {len(body_bytes)} bytes exceeds the {MAX_PAYLOAD_BYTES}-byte limit.",
            status_code=413,
        )

    headers = {
        "Authorization": f"Bearer {VETCOMM_INGEST_TOKEN}",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key,
    }

    async with httpx.AsyncClient(timeout=VETCOMM_STATEMENTS_API_TIMEOUT) as client:
        resp = await client.post(url, content=body_bytes, headers=headers)

    try:
        data = resp.json()
    except Exception:
        data = {}

    if resp.status_code < 300 and isinstance(data, dict) and "error" not in data:
        return data

    error = data.get("error") if isinstance(data, dict) else None
    code = (error or {}).get("code", "internal_error")
    message = (error or {}).get("message", "VetComm statements API request failed.")
    logger.warning("vetcomm submit_statement failed status=%s code=%s", resp.status_code, code)
    raise VetCommStatementsError(code=code, message=message, status_code=resp.status_code, details=error or {})


async def get_statements(user_id: str, latest: bool = False) -> dict[str, Any]:
    """
    Call GET /v1/statements/{user_id}. Returns the parsed response on success.
    Raises VetCommStatementsError on any 4xx/5xx with a structured error body.
    """
    url = f"{VETCOMM_STATEMENTS_API_BASE_URL}/v1/statements/{user_id}"
    params = {"latest": "true"} if latest else None
    headers = {"Authorization": f"Bearer {VETCOMM_READ_TOKEN}"}

    async with httpx.AsyncClient(timeout=VETCOMM_STATEMENTS_API_TIMEOUT) as client:
        resp = await client.get(url, params=params, headers=headers)

    try:
        data = resp.json()
    except Exception:
        data = {}

    if resp.status_code < 300 and isinstance(data, dict) and "error" not in data:
        return data

    error = data.get("error") if isinstance(data, dict) else None
    code = (error or {}).get("code", "internal_error")
    message = (error or {}).get("message", "VetComm statements API request failed.")
    logger.warning("vetcomm get_statements failed status=%s code=%s", resp.status_code, code)
    raise VetCommStatementsError(code=code, message=message, status_code=resp.status_code, details=error or {})
