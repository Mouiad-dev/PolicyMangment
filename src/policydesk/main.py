from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from policydesk.routers import add_routers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, object]]:
    """Start/stop hook. The DB engine is created here in M0.4."""
    yield {}


def create_app() -> FastAPI:
    """Build and return the FastAPI app (Factory)."""
    app = FastAPI(title="PolicyDesk", lifespan=lifespan)
    add_routers(app)
    return app
