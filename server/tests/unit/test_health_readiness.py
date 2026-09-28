"""Tests for readiness failure semantics."""

import asyncio
import time

import pytest
from fastapi import HTTPException

from app.api.v1.health import router as health
from app.api.v1.health.router import readiness_check


@pytest.fixture(autouse=True)
def _no_probe_in_flight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "_vector_probe", None)


class _UnavailableDatabase:
    async def execute(self, statement):
        raise RuntimeError("database unavailable")


class _AvailableDatabase:
    async def execute(self, statement):
        return None

    async def exec(self, statement):
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


class _UnreachableVector:
    """A host that does not exist: the client waits out DNS and the connection."""

    def __init__(self) -> None:
        self.probes = 0

    async def check_ready(self) -> None:
        self.probes += 1
        await asyncio.sleep(30)


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


@pytest.mark.asyncio
async def test_an_unreachable_vector_store_does_not_hold_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "VECTOR_READY_TIMEOUT_SECONDS", 0.05)
    vector = _UnreachableVector()

    started = time.monotonic()
    first = await readiness_check(db=_AvailableDatabase(), storage=_AvailableStorage(), vector=vector)
    second = await readiness_check(db=_AvailableDatabase(), storage=_AvailableStorage(), vector=vector)

    assert time.monotonic() - started < 2
    assert (first.status, first.vector) == ("ready", "unavailable")
    assert second.vector == "unavailable"
    # The second check waits on the probe already in flight instead of starting another.
    assert vector.probes == 1
    health._vector_probe.cancel()  # type: ignore[union-attr]


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
