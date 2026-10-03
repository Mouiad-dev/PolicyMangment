from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from policydesk.core.config import get_settings
from policydesk.core.db.session import Database
from policydesk.routers import add_routers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, object]]:
    """Open the DB engine on startup, dispose it on shutdown."""
    database = Database(get_settings())
    try:
        yield {"database": database}
    finally:
        await database.dispose()


def create_app() -> FastAPI:
    """Build and return the FastAPI app (Factory)."""
    app = FastAPI(title="PolicyDesk", lifespan=lifespan)
    add_routers(app)
    return app
