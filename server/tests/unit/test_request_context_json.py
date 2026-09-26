"""A request context survives the JSON columns that resume work later."""

from __future__ import annotations

import json

import orjson

from app.infra.db.session import json_column_serializer
from app.kernel.contracts.context import RequestContext


def test_a_credential_context_survives_a_json_column() -> None:
    ctx = RequestContext(
        tenant_id="t",
        workspace_id="w",
        user_id="u",
        workspace_role="Dev",
        scopes=frozenset({"write", "read"}),
        api_key_id="key_1",
    )

    stored = orjson.loads(json_column_serializer(ctx.to_json()))

    assert stored["scopes"] == ["read", "write"]
    assert RequestContext.from_json(stored) == ctx


def test_a_session_context_round_trips() -> None:
    ctx = RequestContext(tenant_id="t", workspace_id="w", user_id="u", llm_daily_quota=5)

    assert RequestContext.from_json(json.loads(json.dumps(ctx.to_json()))) == ctx


def test_fields_written_by_a_newer_release_are_ignored() -> None:
    restored = RequestContext.from_json(
        {"tenant_id": "t", "workspace_id": "w", "user_id": "u", "added_later": 1}
    )

    assert (restored.tenant_id, restored.workspace_id, restored.user_id) == ("t", "w", "u")
