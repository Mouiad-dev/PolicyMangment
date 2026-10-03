from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from policydesk.core.config import Settings


class Database:
    """Owns the one async engine + session factory for the process."""

    def __init__(self, settings: Settings) -> None:
        db = settings.db
        # TODO: Pool budget: servers x workers x (size + overflow) + admin < max_connections
        self._engine: AsyncEngine = create_async_engine(
            settings.database_url,
            pool_size=db.pool.size,
            max_overflow=db.pool.max_overflow,
            pool_timeout=db.pool.timeout,
            pool_recycle=db.pool.recycle,
            pool_pre_ping=True,
            connect_args={
                "server_settings": {
                    "statement_timeout": str(db.statement_timeout_ms),
                    "idle_in_transaction_session_timeout": str(db.idle_tx_timeout_ms),
                },
            },
        )
        self._session_factory = async_sessionmaker(bind=self._engine, expire_on_commit=False)

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    def session(self) -> AsyncSession:
        return self._session_factory()

    async def dispose(self) -> None:
        await self._engine.dispose()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request, from the Database in lifespan state."""
    database: Database = request.state.database
    async with database.session() as session:
        yield session
