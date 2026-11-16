"""Pooled PostgreSQL connections start with timeout backstops."""

from __future__ import annotations

from typing import Any

import pytest

from app.infra.db import session as db_session


def test_options_carry_the_timeouts_and_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_session.settings, "database_statement_timeout_ms", 1000)
    monkeypatch.setattr(db_session.settings, "database_idle_in_transaction_timeout_ms", 2000)
    monkeypatch.setattr(db_session.settings, "database_lock_timeout_ms", 300)

    assert db_session.session_options() == (
        "-c timezone=UTC -c statement_timeout=1000 "
        "-c idle_in_transaction_session_timeout=2000 -c lock_timeout=300"
    )


def test_zero_disables_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_session.settings, "database_statement_timeout_ms", 0)
    monkeypatch.setattr(db_session.settings, "database_idle_in_transaction_timeout_ms", 0)
    monkeypatch.setattr(db_session.settings, "database_lock_timeout_ms", 0)

    assert db_session.session_options() == "-c timezone=UTC"


def test_postgres_engine_connects_with_the_options(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_engine(url: str, **kwargs: Any) -> object:
        captured["url"] = url
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(db_session, "create_async_engine", fake_engine)

    db_session.build_async_engine("postgresql+psycopg://u:p@db:5432/soit")

    assert captured["connect_args"] == {"options": db_session.session_options()}
    assert "statement_timeout" in captured["connect_args"]["options"]
