"""Fire-and-forget tasks that are not lost before they finish.

The event loop keeps only a weak reference to a task, so a task created and
dropped can be garbage-collected part way through, and an exception it raises
is reported only as "Task exception was never retrieved". ``spawn`` keeps the
task alive until it is done and logs a failure instead.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)

_running: set[asyncio.Task[Any]] = set()


def _finished(task: asyncio.Task[Any]) -> None:
    _running.discard(task)
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.warning("Background task failed", exc_info=error)


def spawn(coro: Coroutine[Any, Any, Any], *, loop: asyncio.AbstractEventLoop | None = None) -> asyncio.Task[Any]:
    """Schedule ``coro`` on ``loop`` (the running loop by default) and hold it until done."""
    task = (loop or asyncio.get_running_loop()).create_task(coro)
    _running.add(task)
    task.add_done_callback(_finished)
    return task
