"""Session-scoped API credentials and data endpoints."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.lightspeed_api import get_system_info

router = APIRouter(prefix="/session", tags=["session"])


class CredentialsBody(BaseModel):
    api_key: str = Field(..., min_length=1)
    api_secret: str = Field(..., min_length=1)


class CredentialsStatus(BaseModel):
    has_credentials: bool


class DataResponse(BaseModel):
    system_id: str = ""
    system_name: str = ""


def _has_credentials(session: dict) -> bool:
    return bool(session.get("api_key") and session.get("api_secret"))


@router.post("/credentials", response_model=CredentialsStatus)
def save_credentials(request: Request, body: CredentialsBody):
    """Store API key and secret in the current session."""
    session = request.state.session
    session["api_key"] = body.api_key
    session["api_secret"] = body.api_secret
    return CredentialsStatus(has_credentials=True)


@router.get("/credentials", response_model=CredentialsStatus)
def get_credentials_status(request: Request):
    """Return whether the session has credentials (never returns the values)."""
    session = request.state.session
    return CredentialsStatus(has_credentials=_has_credentials(session))


@router.delete("/credentials", response_model=CredentialsStatus)
def clear_credentials(request: Request):
    """Remove API credentials from the session."""
    session = request.state.session
    session.pop("api_key", None)
    session.pop("api_secret", None)
    return CredentialsStatus(has_credentials=False)


@router.get("/data", response_model=DataResponse)
async def pull_data(request: Request):
    """Use session credentials to fetch system id and name from Lightspeed VT API."""
    session = request.state.session
    if not _has_credentials(session):
        raise HTTPException(status_code=401, detail="No credentials in session")
    info = await get_system_info(session["api_key"], session["api_secret"])
    return DataResponse(system_id=info.get("system_id", "") or "", system_name=info.get("system_name", "") or "")
