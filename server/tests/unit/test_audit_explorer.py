"""test_audit_explorer

The audit ledger is only useful if it can be asked a question. These cover
narrowing it by who acted, what they acted on, the outcome, and the window --
the four an investigation actually starts from.
"""

from datetime import timedelta

import pytest

from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.runs.service import RunService


async def _record(
    async_db,
    ctx,
    *,
    actor: str | None = "u_alice",
    resource_type: str = "tool",
    resource_id: str = "plugin:jira.create",
    outcome: str = "succeeded",
    age_hours: int = 1,
) -> None:
    async_db.add(
        AuditEvent(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            run_id="run_1",
            step_id=None,
            event_type="gateway.request",
            resource_type=resource_type,
            resource_id=resource_id,
            operation="invoke",
            actor_user_id=actor,
            outcome=outcome,
            created_at=utc_now() - timedelta(hours=age_hours),
            payload_json={"gateway_type": resource_type},
        )
    )
    await async_db.commit()


def _service(async_db, ctx) -> RunService:
    service = RunService.__new__(RunService)
    service.db = async_db
    service.ctx = ctx
    return service


@pytest.mark.asyncio
async def test_the_ledger_can_be_asked_what_one_person_did(async_db, ctx):
    await _record(async_db, ctx, actor="u_alice")
    await _record(async_db, ctx, actor="u_bob")

    service = _service(async_db, ctx)
    entries = await service.list_audits(actor_user_id="u_alice")

    assert len(entries) == 1
    assert entries[0].actor_user_id == "u_alice"


@pytest.mark.asyncio
async def test_the_ledger_can_be_asked_what_happened_to_one_object(async_db, ctx):
    await _record(async_db, ctx, resource_id="plugin:jira.create")
    await _record(async_db, ctx, resource_id="plugin:pagerduty.page")

    entries = await _service(async_db, ctx).list_audits(resource_id="plugin:pagerduty.page")

    assert [entry.resource_id for entry in entries] == ["plugin:pagerduty.page"]


@pytest.mark.asyncio
async def test_refused_actions_can_be_read_without_paging_the_successes(async_db, ctx):
    await _record(async_db, ctx, outcome="succeeded")
    await _record(async_db, ctx, outcome="denied")

    entries = await _service(async_db, ctx).list_audits(outcome="denied")

    assert [entry.outcome for entry in entries] == ["denied"]


@pytest.mark.asyncio
async def test_the_window_bounds_the_answer(async_db, ctx):
    await _record(async_db, ctx, age_hours=1)
    await _record(async_db, ctx, age_hours=48)

    service = _service(async_db, ctx)
    entries = await service.list_audits(since=utc_now() - timedelta(hours=24))

    assert len(entries) == 1


@pytest.mark.asyncio
async def test_the_count_answers_the_same_question_as_the_listing(async_db, ctx):
    """A total that disagrees with the rows below it is worse than no total."""
    await _record(async_db, ctx, actor="u_alice", outcome="denied")
    await _record(async_db, ctx, actor="u_alice", outcome="succeeded")
    await _record(async_db, ctx, actor="u_bob", outcome="denied")

    service = _service(async_db, ctx)
    filters = {"actor_user_id": "u_alice", "outcome": "denied"}

    assert await service.count_audits(**filters) == len(await service.list_audits(**filters))
    assert await service.count_audits(**filters) == 1


@pytest.mark.asyncio
async def test_an_entry_names_the_actor_and_the_object_not_only_the_run(async_db, ctx):
    """The gateway is how a call was made, not who made it."""
    await _record(async_db, ctx, actor="u_alice", resource_type="tool", resource_id="plugin:jira.create")

    entry = (await _service(async_db, ctx).list_audits())[0]

    assert entry.actor_user_id == "u_alice"
    assert entry.resource_type == "tool"
    assert entry.resource_id == "plugin:jira.create"
    assert entry.operation == "invoke"
    assert entry.created_at is not None
