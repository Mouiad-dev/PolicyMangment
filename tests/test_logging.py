import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from policydesk.core.loggers import JSONFormatter, RequestIdMiddleware, request_id_var


def test_json_formatter_includes_fields() -> None:
    record = logging.LogRecord("policydesk", logging.INFO, __file__, 1, "hello", None, None)
    record.method = "GET"
    token = request_id_var.set("rid-1")
    try:
        output = JSONFormatter().format(record)
    finally:
        request_id_var.reset(token)
    data = json.loads(output)
    assert data["message"] == "hello"
    assert data["level"] == "INFO"
    assert data["request_id"] == "rid-1"
    assert data["method"] == "GET"


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_request_id_echoed() -> None:
    client = TestClient(_app())
    response = client.get("/ping", headers={"X-Request-ID": "abc-123"})
    assert response.headers["x-request-id"] == "abc-123"


def test_request_id_generated_when_absent() -> None:
    client = TestClient(_app())
    response = client.get("/ping")
    request_id = response.headers["x-request-id"]
    assert request_id and request_id != "-"
