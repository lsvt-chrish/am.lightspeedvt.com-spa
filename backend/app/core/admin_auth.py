"""
HTTP Basic auth gate for the ops-dashboard board admin endpoints.

Interim solution: one shared username/password rather than per-user
accounts. If/when multiple named people need distinct logins and an audit
trail of who changed what, replace this with fastapi-users instead.
"""
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import OPS_ADMIN_PASSWORD, OPS_ADMIN_USERNAME

security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    if not OPS_ADMIN_PASSWORD:
        # No password configured: refuse everything rather than running open.
        raise HTTPException(status_code=503, detail="Admin auth not configured")

    username_ok = secrets.compare_digest(credentials.username, OPS_ADMIN_USERNAME)
    password_ok = secrets.compare_digest(credentials.password, OPS_ADMIN_PASSWORD)
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
