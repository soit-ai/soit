"""Tests for readiness failure semantics."""

import pytest
from fastapi import HTTPException

from app.api.v1.health.router import readiness_check


class _UnavailableDatabase:
    def execute(self, statement):
        raise RuntimeError("database unavailable")


class _AvailableDatabase:
    def execute(self, statement):
        return None

    def exec(self, statement):
        return type("Result", (), {"all": lambda self: []})()


class _UnavailableStorage:
    async def ensure_ready(self) -> None:
        raise RuntimeError("storage unavailable")


class _AvailableStorage:
    async def ensure_ready(self) -> None:
        return None


class _ReadyVector:
    async def check_ready(self) -> None:
        return None


class _DownVector:
    async def check_ready(self) -> None:
        raise RuntimeError("vector store unavailable")


@pytest.mark.asyncio
async def test_readiness_returns_service_unavailable_when_database_is_down() -> None:
    with pytest.raises(HTTPException) as error:
        await readiness_check(db=_UnavailableDatabase())

    assert error.value.status_code == 503
    assert error.value.detail == "Database is unavailable"


@pytest.mark.asyncio
async def test_readiness_returns_service_unavailable_when_storage_is_down() -> None:
    with pytest.raises(HTTPException) as error:
        await readiness_check(db=_AvailableDatabase(), storage=_UnavailableStorage())

    assert error.value.status_code == 503
    assert error.value.detail == "Object storage is unavailable"


@pytest.mark.asyncio
async def test_readiness_reports_vector_store_connected() -> None:
    resp = await readiness_check(
        db=_AvailableDatabase(), storage=_AvailableStorage(), vector=_ReadyVector()
    )
    assert resp.status == "ready"
    assert resp.vector == "connected"


@pytest.mark.asyncio
async def test_readiness_stays_ready_but_reports_vector_unavailable() -> None:
    # Vector store is non-gating: a vector outage is reported, not a 503.
    resp = await readiness_check(
        db=_AvailableDatabase(), storage=_AvailableStorage(), vector=_DownVector()
    )
    assert resp.status == "ready"
    assert resp.vector == "unavailable"


def test_metrics_open_by_default(client) -> None:
    assert client.get("/metrics").status_code == 200


def test_metrics_requires_token_when_configured(client) -> None:
    from app.settings.settings import settings

    previous = settings.metrics_token
    settings.metrics_token = "scrape-secret"
    try:
        assert client.get("/metrics").status_code == 401
        assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert (
            client.get("/metrics", headers={"Authorization": "Bearer scrape-secret"}).status_code
            == 200
        )
    finally:
        settings.metrics_token = previous
