"""Deciding an approval request: one decision, taken once.

The same decision sent again changes nothing and sends no second event; a
different decision on a closed request is a conflict, never an overwrite.
"""

from __future__ import annotations

import pytest
from fastapi import status
from sqlmodel import select

from app.kernel.runtime.db.models.events import EventOutbox
from app.modules.observe.domain.models import ApprovalRequest

pytestmark = pytest.mark.asyncio


async def _pending(async_db, ctx) -> str:
    approval = ApprovalRequest(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id="run_decided",
        title="Approve tool call: tool:test:send",
        details_json={"tool_call_id": "call_send"},
    )
    async_db.add(approval)
    await async_db.commit()
    return approval.id


async def _resolution_events(async_db, approval_id: str) -> list[str]:
    rows = (await async_db.exec(select(EventOutbox).where(EventOutbox.subject_id == approval_id))).all()
    events = [row if isinstance(row, EventOutbox) else row[0] for row in rows]
    return sorted(event.event_type for event in events if event.event_type != "approval.requested")


async def test_the_same_decision_again_changes_nothing(async_client, async_db, ctx) -> None:
    approval_id = await _pending(async_db, ctx)
    path = f"/api/v1/observe/approvals/{approval_id}/resolve"

    first = await async_client.post(path, json={"status": "approved", "resolution_note": "ok"})
    again = await async_client.post(path, json={"status": "approved", "resolution_note": "ok again"})

    assert first.status_code == again.status_code == status.HTTP_200_OK, again.text
    assert again.json()["data"]["resolution_note"] == "ok"
    assert await _resolution_events(async_db, approval_id) == ["approval.approved"]


async def test_a_different_decision_on_a_closed_request_is_a_conflict(async_client, async_db, ctx) -> None:
    approval_id = await _pending(async_db, ctx)
    path = f"/api/v1/observe/approvals/{approval_id}/resolve"

    rejected = await async_client.post(path, json={"status": "rejected"})
    approved = await async_client.post(path, json={"status": "approved"})

    assert rejected.status_code == status.HTTP_200_OK
    assert approved.status_code == status.HTTP_409_CONFLICT, approved.text
    stored = await async_db.get(ApprovalRequest, approval_id)
    await async_db.refresh(stored)
    assert stored.status == "rejected"
    assert await _resolution_events(async_db, approval_id) == ["approval.rejected"]
