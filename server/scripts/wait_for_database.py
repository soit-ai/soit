"""Block until the configured PostgreSQL accepts connections.

Compose orders migrations after the bundled database's healthcheck, but the
application stack can also run against a database it does not start, where no
such ordering exists. Waiting here turns a database that is still coming up
into a short delay, and one that never answers into a single clear error
instead of an Alembic traceback.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit, urlunsplit

DEFAULT_TIMEOUT_SECONDS = 60.0
RETRY_INTERVAL_SECONDS = 2.0


def libpq_url(database_url: str) -> str:
    """Drop a SQLAlchemy driver suffix such as `+psycopg`, which libpq rejects."""
    parts = urlsplit(database_url)
    scheme = parts.scheme.split("+", 1)[0]
    return urlunsplit((scheme, *parts[1:]))


def redacted(database_url: str) -> str:
    """Return the URL with its password removed, for error messages."""
    parts = urlsplit(database_url)
    if parts.password is None:
        return database_url
    netloc = parts.netloc.replace(f":{parts.password}@", ":***@", 1)
    return urlunsplit((parts.scheme, netloc, *parts[2:]))


def wait_for_database(
    database_url: str,
    *,
    timeout_seconds: float,
    connect: Callable[..., Any],
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Retry a connection until it succeeds or `timeout_seconds` elapses."""
    deadline = clock() + timeout_seconds
    url = libpq_url(database_url)
    while True:
        try:
            connect(url, connect_timeout=5).close()
            return
        except Exception as exc:  # noqa: BLE001 - any failure means not ready yet
            if clock() >= deadline:
                raise TimeoutError(
                    f"database {redacted(url)} did not accept connections within "
                    f"{timeout_seconds:g}s: {exc}"
                ) from exc
        sleep(RETRY_INTERVAL_SECONDS)


def main() -> int:
    import psycopg

    from app.settings.settings import settings

    timeout = float(os.environ.get("DATABASE_WAIT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    try:
        wait_for_database(
            settings.database_url or "",
            timeout_seconds=timeout,
            connect=psycopg.connect,
        )
    except TimeoutError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
