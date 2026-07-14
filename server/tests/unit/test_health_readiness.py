"""Tests for readiness failure semantics."""

import pytest
from fastapi import HTTPException

from app.api.v1.health.router import readiness_check


class _UnavailableDatabase:
    def execute(self, statement):
        raise RuntimeError("database unavailable")


@pytest.mark.asyncio
async def test_readiness_returns_service_unavailable_when_database_is_down() -> None:
    with pytest.raises(HTTPException) as error:
        await readiness_check(db=_UnavailableDatabase())

    assert error.value.status_code == 503
    assert error.value.detail == "Database is unavailable"
