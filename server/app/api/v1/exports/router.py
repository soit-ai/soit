""" router

Ledger exports: runs, run steps, cost entries, audit entries and outbox
events of one workspace in a time window, as JSON Lines or CSV in the ledger
contract. Exporting is itself recorded in the audit ledger.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.permissions import require_workspace_governance_ctx
from app.infra.db.session import get_async_db
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.runs.ledger import LEDGER_SCHEMA_VERSION
from app.kernel.runtime.runs.ledger_export import (
    check_window,
    iter_ledger_records,
    render,
)

router = APIRouter()

LEDGER_VERSION_HEADER = "x-soit-ledger-schema"
_MEDIA_TYPES = {"jsonl": "application/x-ndjson", "csv": "text/csv; charset=utf-8"}


def _utc_naive(value: datetime) -> datetime:
    """The ledger stores naive UTC; an aware bound is converted, a naive one is UTC."""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


@router.get("/{kind}", response_class=StreamingResponse)
async def export_ledger(
    kind: Literal["runs", "steps", "costs", "audit", "events"],
    since: datetime,
    until: datetime | None = None,
    format: Literal["jsonl", "csv"] = "jsonl",
    ctx: RequestContext = Depends(require_workspace_governance_ctx),
    db: AsyncSession = Depends(get_async_db),
) -> StreamingResponse:
    """Stream one kind of ledger record created in [since, until), oldest first.

    Owners and admins only: an export takes the workspace's evidence out of
    SOIT, so who took what, and when, is written to the audit ledger first.
    """
    start = _utc_naive(since)
    end = _utc_naive(until) if until is not None else utc_now().replace(tzinfo=None)
    check_window(start, end)

    db.add(
        AuditEvent(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            event_type="ledger.exported",
            resource_type="ledger",
            resource_id=kind,
            operation="export",
            actor_user_id=ctx.user_id,
            trace_id=ctx.trace_id,
            outcome="allowed",
            scope="workspace",
            payload_json={
                "since": start.isoformat() + "Z",
                "until": end.isoformat() + "Z",
                "format": format,
                "schema_version": LEDGER_SCHEMA_VERSION,
                "api_key_id": ctx.api_key_id,
            },
        )
    )
    await db.commit()

    records = iter_ledger_records(db, ctx, kind, since=start, until=end)
    filename = f"soit-{kind}-{start:%Y%m%dT%H%M%S}Z-{end:%Y%m%dT%H%M%S}Z.{format}"
    return StreamingResponse(
        render(records, kind, format),
        media_type=_MEDIA_TYPES[format],
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            LEDGER_VERSION_HEADER: LEDGER_SCHEMA_VERSION,
            "Cache-Control": "no-store",
        },
    )
