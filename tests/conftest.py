import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from policydesk.core.config import get_settings
from policydesk.core.db.session import get_session
from policydesk.main import create_app

_MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "src/policydesk/core/db/alembic"


def pytest_configure() -> None:
    """Point every Settings user (app, Alembic, tests) at the `_test` database."""
    name = get_settings().db.name
    if not name.endswith("_test"):
        os.environ["DB__NAME"] = f"{name}_test"
    if "DB__PORT" not in os.environ:  # CI sets its own; else the compose postgres_test port
        os.environ["DB__PORT"] = _env_or_dotenv("TEST_DB_HOST_PORT", "5433")
    get_settings.cache_clear()


def _env_or_dotenv(key: str, default: str) -> str:
    """Same lookup as compose: shell env first, then .env, then the default."""
    return os.environ.get(key) or dotenv_values(".env").get(key) or default


def _alembic_config() -> Config:
    # No alembic.ini: its logging setup would disable our app loggers.
    config = Config()
    config.set_main_option("script_location", str(_MIGRATIONS_DIR))
    return config


@pytest_asyncio.fixture(scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with engine.connect():
            pass
    except Exception:
        await engine.dispose()
        if os.environ.get("CI"):  # GitHub sets CI=true: a missing DB must fail, not skip
            pytest.fail("Postgres not available in CI")
        pytest.skip("Postgres not available")
    config = _alembic_config()
    # env.py calls asyncio.run(), which cannot run inside our loop, so use a thread.
    await asyncio.to_thread(command.upgrade, config, "head")
    yield engine
    await engine.dispose()
    await asyncio.to_thread(command.downgrade, config, "base")


@pytest_asyncio.fixture
async def db_connection(db_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with db_engine.connect() as conn:
        transaction = await conn.begin()
        yield conn
        if transaction.is_active:
            await transaction.rollback()


@pytest_asyncio.fixture
async def db_session(db_connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(
        bind=db_connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    ) as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
