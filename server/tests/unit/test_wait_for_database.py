"""Tests for the pre-migration database wait."""

from __future__ import annotations

import pytest

from scripts.wait_for_database import libpq_url, redacted, wait_for_database


class _Connection:
    def close(self) -> None:
        pass


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_libpq_url_drops_the_sqlalchemy_driver_suffix() -> None:
    assert libpq_url("postgresql+psycopg://u:p@db:5432/soit") == "postgresql://u:p@db:5432/soit"
    assert libpq_url("postgresql://u:p@db:5432/soit") == "postgresql://u:p@db:5432/soit"


def test_redacted_hides_the_password() -> None:
    assert redacted("postgresql://soit:s3cret@db:5432/soit") == "postgresql://soit:***@db:5432/soit"
    assert redacted("postgresql://db:5432/soit") == "postgresql://db:5432/soit"


def test_wait_returns_once_the_database_answers() -> None:
    clock = _FakeClock()
    attempts: list[str] = []

    def connect(url: str, **_: object) -> _Connection:
        attempts.append(url)
        if len(attempts) < 3:
            raise OSError("connection refused")
        return _Connection()

    wait_for_database(
        "postgresql+psycopg://soit:soit@postgres:5432/soit",
        timeout_seconds=60,
        connect=connect,
        sleep=clock.sleep,
        clock=clock,
    )

    assert attempts == ["postgresql://soit:soit@postgres:5432/soit"] * 3


def test_wait_gives_up_with_a_redacted_error() -> None:
    clock = _FakeClock()

    def connect(*_: object, **__: object) -> _Connection:
        raise OSError("connection refused")

    with pytest.raises(TimeoutError) as excinfo:
        wait_for_database(
            "postgresql://soit:s3cret@postgres:5432/soit",
            timeout_seconds=10,
            connect=connect,
            sleep=clock.sleep,
            clock=clock,
        )

    message = str(excinfo.value)
    assert "s3cret" not in message
    assert "within 10s" in message
    assert clock.now >= 10
