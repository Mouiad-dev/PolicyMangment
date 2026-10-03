from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from policydesk.core.config import get_settings
from policydesk.core.db.session import Database
from policydesk.core.errors import register_error_handlers
from policydesk.core.loggers import RequestIdMiddleware, configure_logging
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
    configure_logging(get_settings())
    app = FastAPI(title="PolicyDesk", lifespan=lifespan)
    register_error_handlers(app)
    app.add_middleware(RequestIdMiddleware)
    add_routers(app)
    return app
