from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient

from policydesk.core.db.session import get_session
from policydesk.main import create_app


def test_health_live() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


class _OkSession:
    async def execute(self, *args: Any, **kwargs: Any) -> None:
        return None


class _BrokenSession:
    async def execute(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("db down")


def test_health_ready_ok() -> None:
    async def ok_session() -> AsyncIterator[Any]:
        yield _OkSession()

    app = create_app()
    app.dependency_overrides[get_session] = ok_session
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_ready_down() -> None:
    async def broken_session() -> AsyncIterator[Any]:
        yield _BrokenSession()

    app = create_app()
    app.dependency_overrides[get_session] = broken_session
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "down"}
