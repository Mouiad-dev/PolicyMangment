from fastapi import APIRouter

from policydesk.modules.health.dtos import HealthStatus

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthStatus)
def live() -> HealthStatus:
    """Liveness: the process is up. No database call (FND-14)."""
    return HealthStatus(status="ok")
