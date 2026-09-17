"""One dead-letter view across every execution kind, with honest redrive."""

from datetime import timedelta

import pytest

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.responses import ResponseInteraction
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.deadletter.contracts import (
    DeadLetterKind,
    RedriveOutcome,
    clear_dead_letter_sources,
    registered_kinds,
)
from app.kernel.runtime.deadletter.service import DeadLetterService
from app.kernel.runtime.status import TaskStatus
from app.kernel.runtime.tasks import drivers
from app.modules.knowledge.domain.models import KnowledgeIngestTask
from app.modules.workflow.domain.models import (
    Workflow,
    WorkflowRun,
    WorkflowVersion,
)
from app.modules.workflow.runtime.resume import (
    RESUME_BLOCKED_CHECKPOINT_MISSING,
    RESUME_BLOCKED_POLICY_NEVER,
)
from app.wiring.dead_letter_sources import register_dead_letter_sources


@pytest.fixture(autouse=True)
def _sources():
    clear_dead_letter_sources()
    drivers.clear_task_drivers()
    register_dead_letter_sources()
    yield
    clear_dead_letter_sources()
    drivers.clear_task_drivers()


async def _failed_outbox(async_db, ctx: RequestContext, *, row_id: str, minutes_ago: int) -> None:
    moment = utc_now() - timedelta(minutes=minutes_ago)
    async_db.add(
        EventOutbox(
            id=row_id,
            event_id=f"evt_{row_id}",
            event_type="task.failed",
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            idempotency_key=f"idem_{row_id}",
            status="failed",
            attempt_count=64,
            last_error="consumer exploded",
            failed_consumer_name="observe.task",
            processed_at=moment,
        )
    )
    await async_db.commit()


async def _failed_task(async_db, ctx: RequestContext, *, task_id: str, task_type: str) -> Task:
    task = Task(
        id=task_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        task_type=task_type,
        status=TaskStatus.FAILED.value,
        error_code="BOOM",
        error_message="it broke",
        finished_at=utc_now() - timedelta(minutes=5),
    )
    async_db.add(task)
    await async_db.commit()
    await async_db.refresh(task)
    return task


async def _failed_ingest(async_db, ctx: RequestContext, *, task_id: str) -> KnowledgeIngestTask:
    task = KnowledgeIngestTask(
        id=task_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        knowledge_id="knw_1",
        document_id="doc_1",
        status="failed",
        error_code="INGEST_ERROR",
        error_message="parser failed",
        retry_count=2,
        finished_at=utc_now() - timedelta(minutes=1),
    )
    async_db.add(task)
    await async_db.commit()
    await async_db.refresh(task)
    return task


async def _failed_workflow(async_db, ctx: RequestContext, *, row_id: str) -> WorkflowRun:
    row = WorkflowRun(
        id=row_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=f"run_{row_id}",
        workflow_id="wf_1",
        status="failed",
        completed_nodes=2,
        total_nodes=5,
    )
    async_db.add(row)
    await async_db.commit()
    await async_db.refresh(row)
    return row


async def _resumable_workflow(
    async_db,
    ctx: RequestContext,
    *,
    row_id: str,
    resume_policy: str | None = None,
):
    """A failed run whose first node finished and is stored in a checkpoint."""
    workflow = Workflow(
        id=f"wf_{row_id}",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name=f"workflow-{row_id}",
    )
    version = WorkflowVersion(
        id=f"ver_{row_id}",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        workflow_id=workflow.id,
        version="1.0.0",
        spec_json={
            "name": f"workflow-{row_id}",
            "inputs_schema": {"type": "object", "properties": {}},
            "outputs_schema": {"type": "object", "properties": {"value": {}}},
            "graph": {
                "nodes": [
                    {"id": "a", "type": "set_var", "params": {"key": "x", "value": 1}},
                    {"id": "b", "type": "set_var", "params": {"key": "y", "value": 2}},
                    {"id": "c", "type": "output", "params": {"value": "{{ steps.a.output }}"}},
                ],
                "edges": [
                    {"id": "e1", "from": "a", "to": "b"},
                    {"id": "e2", "from": "b", "to": "c"},
                ],
            },
            **({"semantics": {"resume_policy": resume_policy}} if resume_policy else {}),
        },
    )
    run = Run(
        id=f"run_{row_id}",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        mode="workflow",
        subject_kind="workflow",
        subject_id=workflow.id,
        subject_version_id=version.id,
        status="failed",
    )
    row = WorkflowRun(
        id=row_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=run.id,
        workflow_id=workflow.id,
        status="failed",
        completed_nodes=1,
        total_nodes=3,
        checkpoint_json={
            "inputs": {},
            "node_states": {"a": "succeeded"},
            "node_outputs": {"a": {"x": 1}},
            "truncated_node_ids": [],
        },
    )
    async_db.add(workflow)
    async_db.add(version)
    async_db.add(run)
    async_db.add(row)
    await async_db.commit()
    return workflow, version, run


async def _failed_interaction(async_db, ctx: RequestContext, *, interaction_id: str) -> None:
    async_db.add(
        ResponseInteraction(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            interaction_id=interaction_id,
            thread_id="thread_1",
            request_hash="hash_1",
            status="failed",
            attempt_count=3,
        )
    )
    await async_db.commit()


def test_every_execution_kind_reports_dead_letters():
    assert set(registered_kinds()) == set(DeadLetterKind)


@pytest.mark.asyncio
async def test_dead_letters_from_all_kinds_appear_in_one_view(async_db, ctx):
    await _failed_outbox(async_db, ctx, row_id="outbox_1", minutes_ago=10)
    await _failed_task(async_db, ctx, task_id="task_1", task_type="agent.stream")
    await _failed_ingest(async_db, ctx, task_id="ingest_1")
    await _failed_workflow(async_db, ctx, row_id="wfr_1")
    await _failed_interaction(async_db, ctx, interaction_id="rint_1")

    letters = await DeadLetterService(async_db, ctx).list_dead_letters(limit=50)

    assert {item.kind for item in letters} == set(DeadLetterKind)


@pytest.mark.asyncio
async def test_the_view_can_be_narrowed_to_one_kind(async_db, ctx):
    await _failed_outbox(async_db, ctx, row_id="outbox_1", minutes_ago=10)
    await _failed_task(async_db, ctx, task_id="task_1", task_type="agent.stream")

    letters = await DeadLetterService(async_db, ctx).list_dead_letters(kind=DeadLetterKind.TASK)

    assert [item.id for item in letters] == ["task_1"]


@pytest.mark.asyncio
async def test_newest_failures_come_first_across_kinds(async_db, ctx):
    await _failed_outbox(async_db, ctx, row_id="outbox_old", minutes_ago=60)
    await _failed_ingest(async_db, ctx, task_id="ingest_recent")

    letters = await DeadLetterService(async_db, ctx).list_dead_letters(limit=50)

    # Merging then sorting keeps ordering meaningful; paging per source would
    # have hidden a recent failure behind an older kind.
    assert letters[0].id == "ingest_recent"


@pytest.mark.asyncio
async def test_a_task_is_redrivable_only_when_a_driver_exists(async_db, ctx):
    await _failed_task(async_db, ctx, task_id="task_1", task_type="wf_step")
    service = DeadLetterService(async_db, ctx)

    assert (await service.list_dead_letters(kind=DeadLetterKind.TASK))[0].redrivable is False

    drivers.register_task_driver("wf_step", lambda _db, _task: None)

    assert (await service.list_dead_letters(kind=DeadLetterKind.TASK))[0].redrivable is True


@pytest.mark.asyncio
async def test_redriving_a_task_without_a_driver_is_refused(async_db, ctx):
    await _failed_task(async_db, ctx, task_id="task_1", task_type="wf_step")

    result = await DeadLetterService(async_db, ctx).redrive(
        kind=DeadLetterKind.TASK, dead_letter_id="task_1"
    )

    assert result.outcome is RedriveOutcome.UNSUPPORTED


@pytest.mark.asyncio
async def test_redriving_a_task_with_a_driver_requeues_it(async_db, ctx):
    task = await _failed_task(async_db, ctx, task_id="task_1", task_type="agent.stream")
    drivers.register_task_driver("agent.stream", lambda _db, _task: None)

    result = await DeadLetterService(async_db, ctx).redrive(
        kind=DeadLetterKind.TASK, dead_letter_id=task.id
    )

    await async_db.refresh(task)
    assert result.outcome is RedriveOutcome.REDRIVEN
    assert task.status == TaskStatus.QUEUED.value


@pytest.mark.asyncio
async def test_redriving_an_outbox_row_returns_it_to_the_queue(async_db, ctx):
    await _failed_outbox(async_db, ctx, row_id="outbox_1", minutes_ago=10)

    result = await DeadLetterService(async_db, ctx).redrive(
        kind=DeadLetterKind.OUTBOX_EVENT, dead_letter_id="outbox_1"
    )

    row = await async_db.get(EventOutbox, "outbox_1")
    assert result.outcome is RedriveOutcome.REDRIVEN
    assert row.status == "pending"


@pytest.mark.asyncio
async def test_redriving_a_knowledge_ingest_task_requeues_it(async_db, ctx):
    task = await _failed_ingest(async_db, ctx, task_id="ingest_1")

    result = await DeadLetterService(async_db, ctx).redrive(
        kind=DeadLetterKind.KNOWLEDGE_INGEST, dead_letter_id=task.id
    )

    await async_db.refresh(task)
    assert result.outcome is RedriveOutcome.REDRIVEN
    assert task.status == "queued"
    assert task.error_code is None
    # A stale lease would keep the requeued task from being claimed.
    assert task.lease_owner is None


@pytest.mark.asyncio
async def test_a_workflow_run_without_a_checkpoint_is_not_redrivable(async_db, ctx):
    # No checkpoint means no proof of where the run got to, so resuming could
    # re-enter work that already happened.
    await _failed_workflow(async_db, ctx, row_id="wfr_1")
    service = DeadLetterService(async_db, ctx)

    listed = (await service.list_dead_letters(kind=DeadLetterKind.WORKFLOW_RUN))[0]
    result = await service.redrive(
        kind=DeadLetterKind.WORKFLOW_RUN, dead_letter_id="wfr_1"
    )

    assert listed.redrivable is False
    assert listed.details["resume_blocked_reason"] == RESUME_BLOCKED_CHECKPOINT_MISSING
    assert result.outcome is RedriveOutcome.UNSUPPORTED
    # The row is listed, so it exists; the redrive must not claim otherwise.
    assert result.outcome is not RedriveOutcome.NOT_FOUND


@pytest.mark.asyncio
async def test_a_workflow_run_with_a_safe_checkpoint_is_redrivable(async_db, ctx):
    """Resume is offered only when every unfinished node replays safely."""
    workflow, version, run = await _resumable_workflow(async_db, ctx, row_id="wfr_ok")
    service = DeadLetterService(async_db, ctx)

    listed = (await service.list_dead_letters(kind=DeadLetterKind.WORKFLOW_RUN))[0]

    assert listed.redrivable is True
    assert "resume_blocked_reason" not in listed.details


@pytest.mark.asyncio
async def test_a_workflow_declaring_resume_policy_never_is_not_redrivable(async_db, ctx):
    """An author can refuse resume outright, whatever the effect analysis says."""
    await _resumable_workflow(async_db, ctx, row_id="wfr_never", resume_policy="never")
    service = DeadLetterService(async_db, ctx)

    listed = (await service.list_dead_letters(kind=DeadLetterKind.WORKFLOW_RUN))[0]
    result = await service.redrive(
        kind=DeadLetterKind.WORKFLOW_RUN, dead_letter_id="wfr_never"
    )

    assert listed.redrivable is False
    assert listed.details["resume_blocked_reason"] == RESUME_BLOCKED_POLICY_NEVER
    assert result.outcome is RedriveOutcome.UNSUPPORTED


@pytest.mark.asyncio
async def test_a_failed_interaction_is_never_redriven_automatically(async_db, ctx):
    await _failed_interaction(async_db, ctx, interaction_id="rint_1")

    result = await DeadLetterService(async_db, ctx).redrive(
        kind=DeadLetterKind.RESPONSE_INTERACTION, dead_letter_id="rint_1"
    )

    assert result.outcome is RedriveOutcome.UNSUPPORTED


@pytest.mark.asyncio
async def test_redriving_something_already_recovered_is_reported_not_repeated(async_db, ctx):
    task = await _failed_task(async_db, ctx, task_id="task_1", task_type="agent.stream")
    drivers.register_task_driver("agent.stream", lambda _db, _task: None)
    task.status = TaskStatus.SUCCEEDED.value
    async_db.add(task)
    await async_db.commit()

    result = await DeadLetterService(async_db, ctx).redrive(
        kind=DeadLetterKind.TASK, dead_letter_id=task.id
    )

    assert result.outcome is RedriveOutcome.NOT_DEAD


@pytest.mark.asyncio
async def test_dead_letters_are_scoped_to_the_callers_workspace(async_db, ctx):
    await _failed_task(async_db, ctx, task_id="task_mine", task_type="agent.stream")
    other = RequestContext(
        tenant_id=ctx.tenant_id,
        workspace_id="other-workspace",
        user_id=ctx.user_id,
    )

    assert await DeadLetterService(async_db, other).list_dead_letters() == []


@pytest.mark.asyncio
async def test_one_broken_source_does_not_hide_the_others(async_db, ctx, monkeypatch):
    await _failed_ingest(async_db, ctx, task_id="ingest_1")
    from app.kernel.runtime.deadletter import contracts

    broken = contracts.get_dead_letter_source(DeadLetterKind.TASK)

    def explode(*_args, **_kwargs):
        raise RuntimeError("task table unavailable")

    monkeypatch.setattr(broken, "list_dead_letters", explode)

    letters = await DeadLetterService(async_db, ctx).list_dead_letters()

    # An operator must still see what is failing elsewhere.
    assert [item.kind for item in letters] == [DeadLetterKind.KNOWLEDGE_INGEST]
