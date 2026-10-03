import pytest

from policydesk.core.config import Settings
from policydesk.core.db.session import Database


def test_url_built_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB__HOST", "h")
    monkeypatch.setenv("DB__PORT", "1234")
    monkeypatch.setenv("DB__NAME", "mydb")
    monkeypatch.setenv("DB__USER", "u")
    settings = Settings()
    assert settings.database_url.startswith("postgresql+asyncpg://u:")
    assert settings.database_url.endswith("@h:1234/mydb")


async def test_engine_uses_pool_settings() -> None:
    db = Database(Settings())
    try:
        assert db.engine.sync_engine.pool.size() == 3
    finally:
        await db.dispose()
