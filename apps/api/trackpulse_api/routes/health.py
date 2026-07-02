from fastapi import APIRouter, Request
from sqlalchemy import text

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def liveness():
    """Liveness probe — always returns 200."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness(request: Request):
    """Readiness probe — checks dependencies including DB connectivity."""
    dependencies: dict[str, str] = {}

    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is not None:
        try:
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
            dependencies["db"] = "ok"
        except Exception as e:
            dependencies["db"] = f"error: {e}"

    all_ok = all(v == "ok" for v in dependencies.values())
    status = "ok" if all_ok else "degraded"
    return {"status": status, "dependencies": dependencies}
