"""Close accounts whose withdrawal period has elapsed.

A closure that only happens when somebody remembers to click is not a closure,
so this runs on a loop. It is off by default: a self-hosted deployment should
not discover that a timer has been closing accounts. Production turns it on.

The sweep only acts on requests nobody withdrew. Cancelling is what makes the
pause meaningful, and a cancelled request is simply not due.
"""

from __future__ import annotations

import asyncio
import logging

from app.infra.db.session import get_db_sync

logger = logging.getLogger(__name__)


def sweep_due_account_deletions(limit: int = 50) -> int:
    """Close every account past its pause. Returns how many were closed."""
    from app.wiring.services import build_identity_service

    db = get_db_sync()
    try:
        service = build_identity_service(db=db)
        return service.execute_due_account_deletions(limit=limit)
    finally:
        db.close()


async def run_deletion_sweeper(
    *,
    interval_seconds: float = 3600.0,
    limit: int = 50,
) -> None:
    """Sweep on a loop until cancelled.

    A failed sweep is logged and retried on the next tick rather than ending
    the loop: one unclosable account must not stop every other closure.
    """
    while True:
        try:
            closed = await asyncio.to_thread(sweep_due_account_deletions, limit)
            if closed:
                logger.info("Closed %s account(s) whose withdrawal period elapsed", closed)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Account closure sweep failed")
        await asyncio.sleep(max(1.0, float(interval_seconds)))
