""" shared_client

One pooled ``httpx.AsyncClient`` per event loop for model provider calls.

Provider ports are built per request, and each used to open its own client:
every model call paid a fresh TCP and TLS handshake, and the OpenAI port never
closed its client, so its sockets lingered until garbage collection. Sharing a
client per loop keeps connections alive between calls. The pool is per loop,
not per process, because a client belongs to the loop that first used it: a
worker that runs a fresh loop per job must not inherit a dead one.

Clients are keyed by timeout as well, since a provider's configured timeout is
set on the client. The class is part of the key so that a test which swaps
``httpx.AsyncClient`` gets its own client rather than a cached real one.
"""

from __future__ import annotations

import asyncio
import logging
import weakref
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx

from app.settings.settings import settings

logger = logging.getLogger(__name__)

_ClientKey = tuple[Any, tuple[Any, ...]]

_clients: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[_ClientKey, httpx.AsyncClient]] = (
    weakref.WeakKeyDictionary()
)


def _timeout_key(timeout: httpx.Timeout | float | None) -> tuple[Any, ...]:
    if isinstance(timeout, httpx.Timeout):
        return ("timeout", timeout.connect, timeout.read, timeout.write, timeout.pool)
    return ("seconds", timeout)


def _limits() -> httpx.Limits:
    return httpx.Limits(
        max_connections=int(settings.llm_http_max_connections),
        max_keepalive_connections=int(settings.llm_http_max_keepalive_connections),
        keepalive_expiry=float(settings.llm_http_keepalive_expiry_seconds),
    )


def shared_http_client(timeout: httpx.Timeout | float | None = None) -> httpx.AsyncClient:
    """The running loop's pooled client for ``timeout``.

    Callers must not close it or use it as a context manager. Raises
    ``RuntimeError`` outside a running loop.
    """

    loop = asyncio.get_running_loop()
    client_class = httpx.AsyncClient
    key: _ClientKey = (client_class, _timeout_key(timeout))
    clients = _clients.get(loop)
    if clients is None:
        clients = {}
        _clients[loop] = clients
    client = clients.get(key)
    if client is None or getattr(client, "is_closed", False):
        kwargs: dict[str, Any] = {"follow_redirects": False, "limits": _limits()}
        if timeout is not None:
            kwargs["timeout"] = timeout
        client = client_class(**kwargs)
        clients[key] = client
    return client


async def close_shared_http_clients() -> None:
    """Close the running loop's pooled clients, on shutdown."""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    clients = _clients.pop(loop, None) or {}
    for client in clients.values():
        close = getattr(client, "aclose", None)
        if close is None:
            continue
        try:
            await close()
        except Exception:
            logger.debug("shared_http_client.close_failed", exc_info=True)


@asynccontextmanager
async def pooled_http_client(
    timeout: httpx.Timeout | float | None = None,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """``async with`` form of :func:`shared_http_client`; leaving it keeps the client open."""

    yield shared_http_client(timeout)
