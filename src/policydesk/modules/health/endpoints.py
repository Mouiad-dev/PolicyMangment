from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from policydesk.core.db.session import get_session
from policydesk.modules.health.dtos import HealthStatus, ReadyStatus

router = APIRouter(prefix="/health", tags=["health"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/live", response_model=HealthStatus)
def live() -> HealthStatus:
    """Liveness: the process is up. No database call (FND-14)."""
    return HealthStatus(status="ok")


@router.get("/ready", response_model=ReadyStatus)
async def ready(response: Response, session: SessionDep) -> ReadyStatus:
    """Readiness: run SELECT 1. 200 if the DB answers, else 503"""
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyStatus(status="error", database="down")
    return ReadyStatus(status="ok", database="ok")
