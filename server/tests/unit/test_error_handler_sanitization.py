"""The global error handler does not leak internal exception detail to clients."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.kernel.commons.errors import KernelError
from app.middleware.error_handler import ErrorHandlerMiddleware


def _client_for(exc: Exception) -> TestClient:
    app = FastAPI()
    app.add_middleware(ErrorHandlerMiddleware)

    @app.get("/boom")
    async def boom():
        raise exc

    return TestClient(app, raise_server_exceptions=False)


def test_kernel_error_5xx_message_is_generic_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    client = _client_for(
        KernelError("INTERNAL_ERROR", "Fail connecting to server on 127.0.0.1:19530")
    )
    resp = client.get("/boom")
    assert resp.status_code == 500
    body = str(resp.json())
    assert "19530" not in body  # internal host/port must not leak
    assert "Internal server error" in body


def test_kernel_error_4xx_message_is_preserved(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    client = _client_for(KernelError("VALIDATION_ERROR", "Provider name already exists"))
    resp = client.get("/boom")
    assert resp.status_code == 400
    assert "Provider name already exists" in str(resp.json())


def test_an_unexpected_error_keeps_its_text_out_of_the_response_in_development(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    client = _client_for(RuntimeError("could not reach db.internal:5432 as svc_writer"))

    resp = client.get("/boom")

    assert resp.status_code == 500
    body = str(resp.json())
    assert "db.internal" not in body and "svc_writer" not in body
    assert "RuntimeError" not in body
    assert "Internal server error" in body
