"""Proxy endpoint for VetComm statement generation. Not linked from any nav; direct-URL only."""
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.vetcomm_api import VetCommError, generate_statement

router = APIRouter(prefix="/vetcomm", tags=["vetcomm"])


class Condition(BaseModel):
    name: str
    category: str
    claim_path: str


class VeteranInput(BaseModel):
    in_service_cause: str
    what_developed: str
    medical_care_during_service: str = ""
    current_impact: str


class Regeneration(BaseModel):
    previous_statement: str
    veteran_feedback: str
    attempt_number: int


class StatementRequest(BaseModel):
    condition: Condition
    veteran_input: VeteranInput
    regeneration: Regeneration | None = None


@router.post("/statements")
async def create_statement(payload: StatementRequest):
    request_id = f"lms_{uuid.uuid4().hex[:24]}"
    try:
        result = await generate_statement(
            request_id=request_id,
            condition=payload.condition.model_dump(),
            veteran_input=payload.veteran_input.model_dump(),
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
