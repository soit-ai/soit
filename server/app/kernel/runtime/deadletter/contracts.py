"""Unified dead-letter semantics across execution kinds.

A dead letter is work that reached a terminal failure and will not be retried
automatically. Agent interactions, workflow runs, tasks, knowledge ingestion and
the event outbox each already record that in their own row, with their own
column names and their own idea of what "failed" means. An operator had no way
to see them together, and no uniform way to act on them.

This module deliberately introduces no dead-letter table. Copying terminal state
into a second place means the copy can disagree with the source — a task that
succeeded on retry would still be listed as dead. Instead each kind registers a
*source* that reads its own rows and normalises them, so the domain row stays
the only truth.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext


class DeadLetterKind(str, Enum):
    """Which execution produced the dead letter."""

    RESPONSE_INTERACTION = "response_interaction"
    WORKFLOW_RUN = "workflow_run"
    TASK = "task"
    KNOWLEDGE_INGEST = "knowledge_ingest"
    OUTBOX_EVENT = "outbox_event"


class RedriveOutcome(str, Enum):
    """What a redrive attempt did."""

    REDRIVEN = "redriven"
    """The work was queued to run again."""

    UNSUPPORTED = "unsupported"
    """This kind has no safe automatic redrive."""

    NOT_DEAD = "not_dead"
    """The record is no longer in a terminal failure state."""

    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class DeadLetter:
    """One terminally failed unit of work, in a shape common to all kinds."""

    kind: DeadLetterKind
    id: str
    """Identifier within the kind, and what redrive is addressed to."""

    tenant_id: str
    workspace_id: str
    failed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    attempt_count: int = 0
    run_id: str | None = None
    subject: str | None = None
    """Human-facing pointer: the workflow, agent, document or event type."""

    redrivable: bool = False
    """Whether a redrive exists for this kind. Never guessed at call time."""

    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RedriveResult:
    outcome: RedriveOutcome
    detail: str | None = None
    redriven_as: str | None = None
    """Identifier of the new unit of work, when redrive created one."""


class DeadLetterSource(Protocol):
    """Reads one kind's terminal failures and can redrive them."""

    kind: DeadLetterKind
    redrivable: bool

    def list_dead_letters(
        self,
        db: Session,
        ctx: RequestContext,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[DeadLetter]:
        """Return this kind's dead letters, newest first."""
        ...

    def redrive(self, db: Session, ctx: RequestContext, dead_letter_id: str) -> RedriveResult:
        """Attempt to run the failed work again."""
        ...


_SOURCES: dict[DeadLetterKind, DeadLetterSource] = {}


def register_dead_letter_source(source: DeadLetterSource) -> None:
    """Register the source that owns one execution kind."""
    _SOURCES[source.kind] = source


def get_dead_letter_source(kind: DeadLetterKind) -> DeadLetterSource | None:
    return _SOURCES.get(kind)


def registered_kinds() -> tuple[DeadLetterKind, ...]:
    return tuple(_SOURCES)


def clear_dead_letter_sources() -> None:
    """Drop all registrations. Intended for tests and wiring rebuilds."""
    _SOURCES.clear()


SourceFactory = Callable[[], DeadLetterSource]
