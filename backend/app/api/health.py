from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check():
    """Health check endpoint for Docker and load balancers."""
    return {"status": "healthy"}


@router.get("/ready")
def readiness_check():
    """Readiness check - extend later to verify DB connectivity."""
    return {"status": "ready"}
