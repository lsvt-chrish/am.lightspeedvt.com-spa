"""Proxy endpoint for VetComm statement generation. Not linked from any nav; direct-URL only."""
import hashlib
import logging
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, model_validator

from app.lightspeed_lookup_api import get_user_name
from app.va_form_filler import fill_va_form
from app.vetcomm_api import VetCommError, generate_buddy_statement, generate_statement
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


@router.get("/veteran-name/{user_id}")
async def veteran_name(user_id: str):
    """
    Best-effort prefill for the "veteran name" field on pages embedded
    per-veteran (buddy statements). Never errors -- an empty name just means
    the veteran types it in themselves.
    """
    name = await get_user_name(user_id)
    return {"name": name}


# ---------------------------------------------------------------------------
# Buddy (lay/witness) statements -- see docs/vetcomm-buddy-statement-api.md.
# Separate endpoint from personal statements above: longer, written in the
# witness's voice, and (per that doc) never stored -- no save/resume here.
# ---------------------------------------------------------------------------

BuddyRelationship = Literal["family", "friend", "buddy", "officer", "other"]


class BuddyCondition(BaseModel):
    name: str
    category: str


class Witness(BaseModel):
    relationship: BuddyRelationship
    name: str
    relationship_detail: str
    how_met: str = Field(min_length=5)
    witnessed_event: bool
    witnessed_impact: bool


class EventDetail(BaseModel):
    when: str
    where: str
    what: str = Field(min_length=15)


class ImpactDetail(BaseModel):
    change: str = Field(min_length=15)
    examples: str = ""


class BuddyServiceContext(BaseModel):
    branch_of_service: list[Literal[BRANCHES]] = []
    mos: str = ""


class BuddyRegeneration(BaseModel):
    previous_statement: str
    veteran_feedback: str
    attempt_number: int


class BuddyStatementRequest(BaseModel):
    veteran_name: str
    condition: BuddyCondition
    witness: Witness
    event: EventDetail | None = None
    impact: ImpactDetail | None = None
    service_context: BuddyServiceContext = BuddyServiceContext()
    regeneration: BuddyRegeneration | None = None

    @model_validator(mode="after")
    def _validate_witness_fields(self) -> "BuddyStatementRequest":
        if not self.witness.witnessed_event and not self.witness.witnessed_impact:
            raise ValueError("At least one of witnessed_event or witnessed_impact must be true")
        if self.witness.witnessed_event and self.event is None:
            raise ValueError("event is required when witnessed_event is true")
        if self.witness.witnessed_impact and self.impact is None:
            raise ValueError("impact is required when witnessed_impact is true")
        return self


@router.post("/buddy-statements")
async def create_buddy_statement(payload: BuddyStatementRequest):
    request_id = f"lms_buddy_{uuid.uuid4().hex[:24]}"
    try:
        result = await generate_buddy_statement(
            request_id=request_id,
            veteran_name=payload.veteran_name,
            condition=payload.condition.model_dump(),
            witness=payload.witness.model_dump(),
            event=payload.event.model_dump() if payload.event else None,
            impact=payload.impact.model_dump() if payload.impact else None,
            service_context=payload.service_context.model_dump(),
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


class VAFormRequest(BaseModel):
    veteran_name: str
    witness_name: str
    relationship: BuddyRelationship
    relationship_detail: str = ""
    statement: str


@router.post("/buddy-statements/va-form")
async def download_va_form(payload: VAFormRequest):
    """
    Fills the real VA Form 21-10210 PDF (backend/app/assets/) with what we
    know -- veteran/witness name, relationship checkboxes, and the statement
    text -- and returns it for download. Everything else (SSN, address,
    phone, email, signature) is left blank for the veteran/witness to
    complete by hand, same as the print-preview this replaced.
    """
    pdf_bytes = fill_va_form(
        veteran_name=payload.veteran_name,
        witness_name=payload.witness_name,
        relationship=payload.relationship,
        relationship_detail=payload.relationship_detail,
        statement=payload.statement,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="VA-Form-21-10210.pdf"'},
    )
