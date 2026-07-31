"""Transport schemas for the unified dead-letter view."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.kernel.runtime.deadletter.contracts import (
    DeadLetter,
    DeadLetterKind,
    RedriveOutcome,
)


class DeadLetterResponse(BaseModel):
    """One terminally failed unit of work."""

    kind: DeadLetterKind
    id: str
    failed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    attempt_count: int = 0
    run_id: str | None = None
    subject: str | None = None
    redrivable: bool = False
    """Whether this kind has a safe automatic redrive; never a guess."""

    details: dict[str, Any] = {}

    @classmethod
    def from_domain(cls, item: DeadLetter) -> DeadLetterResponse:
        return cls(
            kind=item.kind,
            id=item.id,
            failed_at=item.failed_at,
            error_code=item.error_code,
            error_message=item.error_message,
            attempt_count=item.attempt_count,
            run_id=item.run_id,
            subject=item.subject,
            redrivable=item.redrivable,
            details=item.details,
        )


class RedriveResponse(BaseModel):
    """Result of asking for one dead letter to run again."""

    outcome: RedriveOutcome
    detail: str | None = None
    redriven_as: str | None = None
