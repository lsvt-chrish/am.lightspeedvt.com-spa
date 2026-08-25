"""Proxy endpoint for VetComm statement generation. Not linked from any nav; direct-URL only."""
import logging
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, model_validator

from app.vetcomm_api import VetCommError, generate_statement

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
    statement: str
    generated_at: datetime


@router.post("/statements/save")
async def save_statement(payload: SavedStatement):
    """
    Placeholder for persisting a generated statement so the veteran can come
    back later to copy it. Not wired to storage yet — just logs and
    acknowledges receipt. TODO: replace with a real table/model once the
    client confirms retention requirements (fields here should stay
    forward-compatible with whatever that ends up being).
    """
    logger.info(
        "vetcomm save_statement placeholder: user_id=%s generated_at=%s chars=%d",
        payload.user_id,
        payload.generated_at.isoformat(),
        len(payload.statement),
    )
    return {"status": "ok"}
