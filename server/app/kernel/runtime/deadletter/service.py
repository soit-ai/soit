"""Query and redrive dead letters across every execution kind."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.deadletter.contracts import (
    DeadLetter,
    DeadLetterKind,
    RedriveOutcome,
    RedriveResult,
    get_dead_letter_source,
    registered_kinds,
)

logger = logging.getLogger(__name__)

MAX_PAGE_SIZE = 200


class DeadLetterService:
    """One view over work that failed terminally, whatever produced it."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def list_dead_letters(
        self,
        *,
        kind: DeadLetterKind | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DeadLetter]:
        """Return dead letters, newest first, across kinds or within one.

        Each source is queried for the full window and the merged result is
        sorted, so paging across kinds cannot silently drop the older entries
        of a kind that happens to be listed later.
        """
        page = max(1, min(int(limit), MAX_PAGE_SIZE))
        skip = max(0, int(offset))
        kinds = (kind,) if kind is not None else registered_kinds()

        collected: list[DeadLetter] = []
        for entry in kinds:
            source = get_dead_letter_source(entry)
            if source is None:
                continue
            try:
                collected.extend(
                    source.list_dead_letters(
                        self.db, self.ctx, limit=page + skip, offset=0
                    )
                )
            except Exception:
                # One kind failing to report must not blind the operator to the
                # others.
                logger.exception(
                    "Dead letter source failed to list", extra={"kind": entry.value}
                )

        collected.sort(
            key=lambda item: (item.failed_at is not None, item.failed_at),
            reverse=True,
        )
        return collected[skip : skip + page]

    def redrive(self, *, kind: DeadLetterKind, dead_letter_id: str) -> RedriveResult:
        """Attempt to run one dead letter again."""
        source = get_dead_letter_source(kind)
        if source is None:
            return RedriveResult(
                outcome=RedriveOutcome.UNSUPPORTED,
                detail=f"No dead letter source is registered for {kind.value}",
            )
        result = source.redrive(self.db, self.ctx, dead_letter_id)
        logger.info(
            "Dead letter redrive %s",
            result.outcome.value,
            extra={"kind": kind.value, "dead_letter_id": dead_letter_id},
        )
        return result
