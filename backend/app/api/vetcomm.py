"""Proxy endpoint for VetComm statement generation. Not linked from any nav; direct-URL only."""
import hashlib
import logging
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, model_validator

from app.vetcomm_api import VetCommError, generate_statement
from app.vetcomm_statements_api import VetCommStatementsError, get_statements, submit_statement

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vetcomm", tags=["vetcomm"])

# Exact strings VetComm expects for branch of service. Must match verbatim.
BRANCHES = (
    "Air Force",
    "Army",
    "Coast Guard",
    "Marine Corps",
    "Merchant Marines",
    "National Guard",
    "Navy",
    "Space Force",
)


class Condition(BaseModel):
    name: str
    category: str
    claim_path: str


class ServiceContext(BaseModel):
    branch_of_service: list[Literal[BRANCHES]]
    mos: str


class VeteranInput(BaseModel):
    in_service_cause: str
    # Required except when condition.claim_path == "secondary" (see
    # StatementRequest validator below).
    happened_on_deployment: bool | None = None
    # Required when happened_on_deployment is true; must be omitted otherwise.
    combat_deployment: bool | None = None
    what_developed: str
    medical_care_during_service: str = ""
    current_impact: str


class Regeneration(BaseModel):
    previous_statement: str
    veteran_feedback: str
    attempt_number: int


class StatementRequest(BaseModel):
    condition: Condition
    service_context: ServiceContext
    veteran_input: VeteranInput
    regeneration: Regeneration | None = None

    @model_validator(mode="after")
    def _validate_deployment_fields(self) -> "StatementRequest":
        is_secondary = self.condition.claim_path == "secondary"
        happened = self.veteran_input.happened_on_deployment
        combat = self.veteran_input.combat_deployment

        if is_secondary:
            if happened is not None or combat is not None:
                raise ValueError(
                    "happened_on_deployment/combat_deployment must be omitted when claim_path is 'secondary'"
                )
            return self

        if happened is None:
            raise ValueError("happened_on_deployment is required unless claim_path is 'secondary'")
        if happened:
            if combat is None:
                raise ValueError("combat_deployment is required when happened_on_deployment is true")
        elif combat is not None:
            raise ValueError("combat_deployment must be omitted when happened_on_deployment is false")
        return self


@router.post("/statements")
async def create_statement(payload: StatementRequest):
    request_id = f"lms_{uuid.uuid4().hex[:24]}"
    try:
        result = await generate_statement(
            request_id=request_id,
            condition=payload.condition.model_dump(),
            service_context=payload.service_context.model_dump(),
            veteran_input=payload.veteran_input.model_dump(exclude_none=True),
            regeneration=payload.regeneration.model_dump() if payload.regeneration else None,
        )
    except VetCommError as e:
        raise HTTPException(
            status_code=e.status_code if e.status_code in (400, 401, 429) else 502,
            detail={"code": e.code, "message": e.message, **e.details},
        )
    return {
        "statement": result.get("statement"),
        "character_count": result.get("character_count"),
        "attempt_number": result.get("attempt_number"),
    }


class SavedStatement(BaseModel):
    user_id: str
    generated_at: datetime
    # The exact request sent to VetComm's /statements/generate for this
    # statement, so the full interaction (inputs + output) is stored
    # together rather than just the final text.
    request: StatementRequest
    statement: str
    character_count: int
    attempt_number: int


@router.post("/statements/save")
async def save_statement(payload: SavedStatement):
    """
    Persists a generated statement (plus the request that produced it) via
    the VetComm statements ingest API, so the veteran can come back later to
    copy it and the full interaction is retrievable, not just the final text.
    """
    # Deterministic per (user, attempt, statement) so a retried "Save" click
    # on the same statement is idempotent server-side rather than creating a
    # duplicate record; a different statement/attempt naturally gets a new key.
    statement_hash = hashlib.sha256(payload.statement.encode()).hexdigest()[:16]
    idempotency_key = f"user-{payload.user_id}-attempt-{payload.attempt_number}-{statement_hash}"

    try:
        result = await submit_statement(
            user_id=payload.user_id,
            statement=payload.statement,
            idempotency_key=idempotency_key,
            generated_at=payload.generated_at.isoformat(),
            condition_name=payload.request.condition.name,
            condition_category=payload.request.condition.category,
            attempt_number=payload.attempt_number,
            character_count=payload.character_count,
            request=payload.request.model_dump(),
        )
    except VetCommStatementsError as e:
        raise HTTPException(
            status_code=e.status_code if e.status_code in (400, 401, 404, 413, 422) else 502,
            detail={"code": e.code, "message": e.message, **e.details},
        )
    return {"status": "ok", "id": result.get("id"), "created": result.get("created")}


@router.get("/statements/{user_id}/latest")
async def get_latest_statement(user_id: str):
    """
    Lets the frontend resume a previously saved statement on page load
    instead of starting from a blank form. Returns `{"found": false}`
    (not an error) whenever there's nothing to resume -- no saved record,
    or a record missing the `request` payload this app needs to rebuild
    the form (e.g. a legacy/malformed row).
    """
    try:
        result = await get_statements(user_id, latest=True)
    except VetCommStatementsError as e:
        if e.code == "not_found":
            return {"found": False}
        raise HTTPException(
            status_code=e.status_code if e.status_code in (400, 401, 404, 422) else 502,
            detail={"code": e.code, "message": e.message, **e.details},
        )

    # ?latest=true responds with the same {user_id, total, data} envelope as
    # the list endpoint -- data is just a single record object here instead
    # of an array. The record's own `payload` (what we submitted beyond the
    # API's first-class fields) is where our original `request` lives.
    record = result.get("data") or {}
    request = (record.get("payload") or {}).get("request")
    if not request:
        return {"found": False}

    return {
        "found": True,
        "statement": record.get("statement"),
        "character_count": record.get("character_count"),
        "attempt_number": record.get("attempt_number"),
        "request": request,
    }
