"""A KernelError whose code has no status answers 500 without its message."""

from __future__ import annotations

import logging

import pytest

from app.api.v1.billing.dependencies import get_credit_service
from app.api.v1.modelhub.dependencies import get_modelhub_service
from app.kernel.commons.errors import KernelError
from app.main import app


def _vault_write_failure() -> KernelError:
    return KernelError(
        "SECRETS_WRITE_FAILED",
        "Failed to write secret: vault.internal:8200 refused svc_writer",
        {"host": "vault.internal"},
    )


def _raising(exc: KernelError):
    def dependency():
        raise exc

    return dependency


async def _get(async_client, path: str, dependency, exc: KernelError):
    app.dependency_overrides[dependency] = _raising(exc)
    try:
        return await async_client.get(path)
    finally:
        app.dependency_overrides.pop(dependency, None)


@pytest.mark.asyncio
async def test_an_unmapped_code_answers_without_its_message_outside_development(
    async_client, monkeypatch, caplog
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")

    with caplog.at_level(logging.ERROR, logger="app.main"):
        response = await _get(
            async_client, "/api/v1/billing/credits/balance", get_credit_service, _vault_write_failure()
        )

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "SECRETS_WRITE_FAILED"
    assert body["message"] == "Internal server error"
    assert body["details"] == {}
    assert "vault.internal" not in response.text
    assert any("vault.internal:8200" in record.getMessage() for record in caplog.records)


@pytest.mark.asyncio
async def test_the_v1_surface_answers_it_in_the_openai_shape(async_client, monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")

    response = await _get(async_client, "/v1/models", get_modelhub_service, _vault_write_failure())

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["message"] == "Internal server error"
    assert error["code"] == "secrets_write_failed"
    assert "vault.internal" not in response.text


@pytest.mark.asyncio
async def test_a_code_with_a_status_keeps_its_message(async_client, monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")

    response = await _get(
        async_client,
        "/api/v1/billing/credits/balance",
        get_credit_service,
        KernelError("CRAWLER_FETCH_FAILED", "Fetch source URI failed with status 404"),
    )

    assert response.status_code == 502
    assert response.json()["message"] == "Fetch source URI failed with status 404"


@pytest.mark.asyncio
async def test_development_answers_with_the_message(async_client, monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")

    response = await _get(
        async_client, "/api/v1/billing/credits/balance", get_credit_service, _vault_write_failure()
    )

    assert response.status_code == 500
    body = response.json()
    assert body["message"] == "Failed to write secret: vault.internal:8200 refused svc_writer"
    assert body["details"] == {"host": "vault.internal"}
