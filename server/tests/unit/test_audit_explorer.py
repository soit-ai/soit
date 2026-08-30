"""test_audit_explorer

The audit ledger is only useful if it can be asked a question. These cover
narrowing it by who acted, what they acted on, the outcome, and the window --
the four an investigation actually starts from.
"""

from datetime import timedelta

from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.runs.service import RunService


def _record(
    db,
    ctx,
    *,
    actor: str | None = "u_alice",
    resource_type: str = "tool",
    resource_id: str = "plugin:jira.create",
    outcome: str = "succeeded",
    age_hours: int = 1,
) -> None:
    db.add(
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
    db.commit()


def _service(db, ctx) -> RunService:
    service = RunService.__new__(RunService)
    service.db = db
    service.ctx = ctx
    return service


def test_the_ledger_can_be_asked_what_one_person_did(db, ctx):
    _record(db, ctx, actor="u_alice")
    _record(db, ctx, actor="u_bob")

    service = _service(db, ctx)
    entries = service.list_audits(actor_user_id="u_alice")

    assert len(entries) == 1
    assert entries[0].actor_user_id == "u_alice"


def test_the_ledger_can_be_asked_what_happened_to_one_object(db, ctx):
    _record(db, ctx, resource_id="plugin:jira.create")
    _record(db, ctx, resource_id="plugin:pagerduty.page")

    entries = _service(db, ctx).list_audits(resource_id="plugin:pagerduty.page")

    assert [entry.resource_id for entry in entries] == ["plugin:pagerduty.page"]


def test_refused_actions_can_be_read_without_paging_the_successes(db, ctx):
    _record(db, ctx, outcome="succeeded")
    _record(db, ctx, outcome="denied")

    entries = _service(db, ctx).list_audits(outcome="denied")

    assert [entry.outcome for entry in entries] == ["denied"]


def test_the_window_bounds_the_answer(db, ctx):
    _record(db, ctx, age_hours=1)
    _record(db, ctx, age_hours=48)

    service = _service(db, ctx)
    entries = service.list_audits(since=utc_now() - timedelta(hours=24))

    assert len(entries) == 1


def test_the_count_answers_the_same_question_as_the_listing(db, ctx):
    """A total that disagrees with the rows below it is worse than no total."""
    _record(db, ctx, actor="u_alice", outcome="denied")
    _record(db, ctx, actor="u_alice", outcome="succeeded")
    _record(db, ctx, actor="u_bob", outcome="denied")

    service = _service(db, ctx)
    filters = {"actor_user_id": "u_alice", "outcome": "denied"}

    assert service.count_audits(**filters) == len(service.list_audits(**filters))
    assert service.count_audits(**filters) == 1


def test_an_entry_names_the_actor_and_the_object_not_only_the_run(db, ctx):
    """The gateway is how a call was made, not who made it."""
    _record(db, ctx, actor="u_alice", resource_type="tool", resource_id="plugin:jira.create")

    entry = _service(db, ctx).list_audits()[0]

    assert entry.actor_user_id == "u_alice"
    assert entry.resource_type == "tool"
    assert entry.resource_id == "plugin:jira.create"
    assert entry.operation == "invoke"
    assert entry.created_at is not None
