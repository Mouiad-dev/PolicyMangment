from fastapi import FastAPI
from fastapi.testclient import TestClient

from policydesk.core.errors import NotFound, register_error_handlers


def _build_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/notfound")
    async def notfound() -> None:
        raise NotFound("policy 7 not found")

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("kaboom")

    return app


def test_app_error_shape() -> None:
    client = TestClient(_build_app())
    response = client.get("/notfound")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "policy 7 not found"}}


def test_unexpected_is_500_without_stack() -> None:
    client = TestClient(_build_app(), raise_server_exceptions=False)
    response = client.get("/boom")
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}
    }
