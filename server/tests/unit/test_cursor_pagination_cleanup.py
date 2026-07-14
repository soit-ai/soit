"""Unit tests for cursor pagination cleanup."""

import base64
import json
from datetime import UTC, datetime

from app.infra.db.pagination import PageToken, decode_cursor_token, encode_cursor_token


def test_encode_cursor_token_requires_cursor_position():
    assert encode_cursor_token(scope="responses", limit=20) is None


def test_decode_cursor_token_rejects_legacy_offset_only_tokens():
    legacy_token = base64.b64encode(
        json.dumps({"scope": "responses", "limit": 15, "offset": 30}).encode("utf-8")
    ).decode("utf-8")

    limit, cursor_at, cursor_id = decode_cursor_token(legacy_token, expected_scope="responses")

    assert limit == 20
    assert cursor_at is None
    assert cursor_id is None


def test_decode_cursor_token_preserves_canonical_cursor_tokens():
    token = encode_cursor_token(
        scope="responses",
        limit=15,
        cursor_at=datetime(2026, 4, 9, 12, 30, tzinfo=UTC),
        cursor_id="resp_123",
    )

    limit, cursor_at, cursor_id = decode_cursor_token(token, expected_scope="responses")

    assert limit == 15
    assert cursor_at == datetime(2026, 4, 9, 12, 30, tzinfo=UTC)
    assert cursor_id == "resp_123"


def test_page_token_rejects_direct_json_tokens():
    raw_token = json.dumps({"offset": 10, "limit": 20})

    try:
        PageToken.from_string(raw_token)
    except ValueError:
        return

    raise AssertionError("Expected direct JSON page token to be rejected")
