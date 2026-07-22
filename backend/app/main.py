from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    apl as apl_api,
    certifications as cert_api,
    completions_mapping as completions_mapping_api,
    health,
    monday_boards as monday_boards_api,
    monday_webhook as monday_webhook_api,
    ops_dashboard as ops_dashboard_api,
    scan as scan_api,
    session as session_api,
    training_export as training_export_api,
    user_check as user_check_api,
    vetcomm as vetcomm_api,
)
from app.core.config import HOST, PORT
from app.core.logging import setup_logging
from app.core.session import SessionMiddleware

setup_logging()

app = FastAPI(
    title="AM Lightspeed VT API",
    description="Backend API for am.lightspeedvt.com",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware)

app.include_router(health.router)
app.include_router(scan_api.router)
app.include_router(session_api.router)
app.include_router(cert_api.router)
app.include_router(training_export_api.router)
app.include_router(completions_mapping_api.router)
app.include_router(user_check_api.router)
app.include_router(apl_api.router)
app.include_router(monday_webhook_api.router)
app.include_router(monday_boards_api.router)
app.include_router(ops_dashboard_api.router)
app.include_router(vetcomm_api.router)


@app.get("/")
def root():
    return {"message": "AM Lightspeed VT API App"}


# Used when running as: python -m app.main
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
