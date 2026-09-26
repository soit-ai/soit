""" ledger_export

Ledger records of one kind in a time window, oldest first, as JSON Lines or
CSV. JSONL carries the contract version in every envelope; CSV columns are
the contract's fields in contract order, and whoever serves the file names
the version beside it. Records are read in keyset batches, so exporting a
busy quarter holds one batch in memory at a time.
"""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timedelta
from typing import Any

import orjson
from sqlalchemy import and_, or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStep
from app.kernel.runtime.runs import ledger
from app.kernel.specs import load_schema

EXPORT_KINDS: dict[str, tuple[str, Any, Callable[[Any], dict[str, Any]]]] = {
    "runs": ("run", Run, ledger.run_record),
    "steps": ("step", RunStep, ledger.step_record),
    "costs": ("cost", RunCostEntry, ledger.cost_record),
    "audit": ("audit", AuditEvent, ledger.audit_record),
    "events": ("event", EventOutbox, ledger.event_record),
}
EXPORT_FORMATS = ("jsonl", "csv")
MAX_EXPORT_WINDOW = timedelta(days=92)
EXPORT_BATCH_SIZE = 500


def check_window(since: datetime, until: datetime) -> None:
    """Refuse a window that is empty, backwards, or longer than a quarter."""
    if until <= since:
        raise ValidationError("until must be after since", {"param": "until"})
    if until - since > MAX_EXPORT_WINDOW:
        raise ValidationError(
            f"An export covers at most {MAX_EXPORT_WINDOW.days} days; split the window",
            {"param": "since", "max_days": MAX_EXPORT_WINDOW.days},
        )


async def iter_ledger_records(
    session: AsyncSession,
    ctx: RequestContext,
    kind: str,
    *,
    since: datetime,
    until: datetime,
    batch_size: int = EXPORT_BATCH_SIZE,
) -> AsyncIterator[dict[str, Any]]:
    """Every record of ``kind`` created in [since, until) in ``ctx``'s workspace, oldest first."""
    record_type, model, write = EXPORT_KINDS[kind]
    last: tuple[datetime, str] | None = None
    while True:
        clauses = [
            model.tenant_id == ctx.tenant_id,
            model.workspace_id == ctx.workspace_id,
            model.created_at >= since,
            model.created_at < until,
        ]
        if last is not None:
            created_at, record_id = last
            clauses.append(
                or_(
                    model.created_at > created_at,
                    and_(model.created_at == created_at, model.id > record_id),
                )
            )
        query = (
            select(model)
            .where(and_(*clauses))
            .order_by(model.created_at, model.id)
            .limit(batch_size)
        )
        rows = list((await session.exec(query)).all())
        for row in rows:
            yield ledger.envelope(record_type, write(row))
        if len(rows) < batch_size:
            return
        last = (rows[-1].created_at, rows[-1].id)


def csv_columns(kind: str) -> list[str]:
    record_type = EXPORT_KINDS[kind][0]
    return list(load_schema(ledger.LEDGER_SPEC)["$defs"][record_type]["properties"])


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict | list):
        return orjson.dumps(value, option=orjson.OPT_SORT_KEYS).decode()
    return str(value)


async def render(
    records: AsyncIterator[dict[str, Any]],
    kind: str,
    export_format: str,
) -> AsyncIterator[bytes]:
    """The export body, one chunk per record (JSONL) or per header and row (CSV)."""
    if export_format == "jsonl":
        async for document in records:
            yield orjson.dumps(document) + b"\n"
        return
    columns = csv_columns(kind)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    yield buffer.getvalue().encode("utf-8")
    async for document in records:
        buffer.seek(0)
        buffer.truncate()
        record = document["record"]
        writer.writerow([_csv_cell(record.get(column)) for column in columns])
        yield buffer.getvalue().encode("utf-8")
