"""Transaction-scoped sequence allocation.

A repository that numbers rows (response events, thread messages) locks the
parent row and reads ``MAX(sequence)`` once per transaction. Every further
allocation for the same parent inside that transaction is a counter increment:
the lock held until commit is what guarantees nobody else numbers rows for
that parent meanwhile. The counters are forgotten when the transaction ends,
whichever way it ends.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlmodel.ext.asyncio.session import AsyncSession

_INFO_KEY = "sequence_cursors"


async def allocate_sequence(
    db: AsyncSession,
    scope: str,
    parent_id: str,
    read_next: Callable[[], Awaitable[int]],
) -> int:
    """Return the next sequence for ``parent_id`` within the current transaction.

    ``read_next`` locks the parent row and reads the next free sequence from
    the database; it runs only for the first allocation per transaction.
    """
    sync_session = getattr(db, "sync_session", None)
    if sync_session is None:
        # A stand-in session (tests) has no transaction to scope a counter to.
        return await read_next()
    cursors: dict[tuple[str, str], int] = sync_session.info.setdefault(_INFO_KEY, {})
    key = (scope, parent_id)
    if key in cursors:
        cursors[key] += 1
        return cursors[key]
    value = await read_next()
    cursors[key] = value
    return value


@event.listens_for(Session, "after_commit", propagate=True)
@event.listens_for(Session, "after_rollback", propagate=True)
@event.listens_for(Session, "after_soft_rollback", propagate=True)
def _forget_cursors(session: Session, *_args: object) -> None:
    session.info.pop(_INFO_KEY, None)
