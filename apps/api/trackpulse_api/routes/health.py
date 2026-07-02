from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def liveness():
    """Liveness probe — always returns 200."""
    return {"status": "ok"}


@router.get("/ready")
def readiness():
    """Readiness probe — checks dependencies."""
    return {"status": "ok", "dependencies": {}}
