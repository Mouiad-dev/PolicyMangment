from fastapi import FastAPI

from policydesk.modules.health.endpoints import router as health_router


def add_routers(app: FastAPI) -> None:
    app.include_router(health_router)
