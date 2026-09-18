"""JSON columns encode with orjson without changing what stored payloads look like."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import orjson
import pytest
from sqlalchemy import select

from app.infra.db.session import json_column_serializer
from app.modules.identity.domain.models import Workspace


def test_int_keys_are_written_as_strings_like_the_stdlib_did() -> None:
    payload = {1: "one", "nested": {2: [3, {"x": None}]}, "unicode": "café", "float": 1.5}

    encoded = json_column_serializer(payload)

    assert orjson.loads(encoded) == json.loads(json.dumps(payload))
    assert isinstance(encoded, str)
    assert "café" in encoded  # no ASCII escaping either way


def test_datetimes_encode_instead_of_failing() -> None:
    moment = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)

    assert orjson.loads(json_column_serializer({"at": moment})) == {"at": "2026-09-18T12:00:00+00:00"}


@pytest.mark.asyncio
async def test_a_json_column_round_trips_through_the_engine(async_db) -> None:
    payload = {"attempt": 1, "tags": ["a", "b"], "nested": {"k": 2.5}, "text": "café"}
    workspace = Workspace(tenant_id="tenant-json", name="json round trip", metadata_json=payload)
    async_db.add(workspace)
    await async_db.commit()
    async_db.expunge_all()

    stored = (await async_db.exec(select(Workspace).where(Workspace.id == workspace.id))).scalars().one()
    assert stored.metadata_json == payload
