"""test_approval_ledger

An approval used to live only in the interrupt it was raised on: whoever was
watching the stream could answer it, and nobody else could see it existed.
These cover the record written alongside the interrupt, and the decision that
closes it.
"""

import pytest
from sqlmodel import select

from app.kernel.commons.time import utc_now
from app.kernel.ports.approvals import ApprovalRecord
from app.kernel.runtime.status import ApprovalStatus
from app.modules.observe.domain.models import ApprovalRequest


class _Ledger:
    """The recording side of the port, without the database behind it."""

    def __init__(self) -> None:
        self.pending: list[ApprovalRecord] = []
        self.decisions: list[dict] = []

    def record_pending(self, ctx, record: ApprovalRecord) -> str | None:
        self.pending.append(record)
        return f"apr_{len(self.pending)}"

    def record_decision(self, ctx, *, run_id, tool_call_id, approved, decided_by=None) -> None:
        self.decisions.append(
            {"run_id": run_id, "tool_call_id": tool_call_id, "approved": approved}
        )


def _agent_service(ctx, ledger):
    from app.modules.agent.application.service import AgentService

    service = AgentService.__new__(AgentService)
    service.ctx = ctx
    service.approval_checkpoint_gateway = None
    service.approval_ledger = ledger
    return service


def _require(service, *, data, resumed=None):
    """Run the approval gate the way the agent loop does."""
    from app.modules.agent.application.service import AgentService

    service._approval_response = lambda _data, _interrupt: resumed
    return AgentService._require_tool_approval(
        service,
        data=data,
        run_id="run_1",
        tool_call_id="call_1",
        tool_ref="plugin:pagerduty.page",
        tool_type="plugin",
        parameters={"service": "checkout"},
        tool_policy={"approval": {"mode": "required", "risk_level": "high"}},
    )


class _Request:
    task_id = "tsk_1"
    thread_id = "thr_1"
    agent_id = "agt_1"


def test_a_tool_call_that_stops_for_approval_is_recorded(ctx):
    from app.modules.agent.application.service import _AgentApprovalInterrupt

    ledger = _Ledger()
    service = _agent_service(ctx, ledger)

    with pytest.raises(_AgentApprovalInterrupt):
        _require(service, data=_Request())

    assert len(ledger.pending) == 1
    record = ledger.pending[0]
    assert record.run_id == "run_1"
    assert record.task_id == "tsk_1"
    assert record.tool_call_id == "call_1"
    assert record.details["tool_ref"] == "plugin:pagerduty.page"
    assert record.details["risk_level"] == "high"
    assert record.policy_ref == "tool_spec:plugin:pagerduty.page"


def test_an_approval_decision_closes_the_record_it_was_raised_on(ctx):
    ledger = _Ledger()
    service = _agent_service(ctx, ledger)

    outcome = _require(
        service,
        data=_Request(),
        resumed={"status": "resolved", "payload": {"decision": "approved"}},
    )

    assert outcome["approved"] is True
    assert ledger.decisions == [
        {"run_id": "run_1", "tool_call_id": "call_1", "approved": True}
    ]


def test_a_rejection_is_recorded_as_one(ctx):
    ledger = _Ledger()
    service = _agent_service(ctx, ledger)

    outcome = _require(
        service,
        data=_Request(),
        resumed={"status": "resolved", "payload": {"decision": "rejected"}},
    )

    assert outcome["approved"] is False
    assert ledger.decisions[0]["approved"] is False


def test_a_rehearsal_never_queues_a_person_for_a_decision():
    """A release test that pages someone for approval is not a test."""
    import inspect

    from app.modules.agent.application.application_service import (
        AgentApplicationService,
    )

    source = inspect.getsource(AgentApplicationService._build_runner)

    assert "approval_ledger=None if sandbox else self.approval_ledger" in source


@pytest.fixture
def sync_session(db):
    """Point the adapter's own session factory at this test's database.

    The adapter opens its own session on purpose -- the run's transaction is
    mid-flight -- so a test of it has to make that session reach the same rows.
    """
    from sqlalchemy.orm import sessionmaker
    from sqlmodel import Session as SqlModelSession

    from app.infra.db import session as db_session

    engine = db.get_bind()
    previous_engine = db_session._engine
    previous_factory = db_session._SessionLocal
    db_session._engine = engine
    db_session._SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine, class_=SqlModelSession
    )
    try:
        yield
    finally:
        db_session._engine = previous_engine
        db_session._SessionLocal = previous_factory


def _pending(ctx, tool_call_id: str) -> ApprovalRequest:
    return ApprovalRequest(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id="run_1",
        title=f"Approve tool call: {tool_call_id}",
        status=ApprovalStatus.PENDING.value,
        details_json={"tool_call_id": tool_call_id},
        created_at=utc_now(),
    )


@pytest.mark.usefixtures("sync_session")
def test_the_decision_closes_only_the_call_it_belongs_to(db, ctx):
    """One run can be waiting on more than one tool call."""
    from app.wiring.container import ObserveApprovalLedger

    db.add(_pending(ctx, "call_a"))
    db.add(_pending(ctx, "call_b"))
    db.commit()

    ObserveApprovalLedger().record_decision(
        ctx, run_id="run_1", tool_call_id="call_a", approved=True
    )

    db.expire_all()
    rows = {
        (row.details_json or {}).get("tool_call_id"): row.status
        for row in db.exec(select(ApprovalRequest)).all()
    }
    assert rows == {
        "call_a": ApprovalStatus.APPROVED.value,
        "call_b": ApprovalStatus.PENDING.value,
    }


@pytest.mark.usefixtures("sync_session")
def test_a_decision_with_nothing_pending_behind_it_is_not_an_error(ctx):
    """The run has already acted; a missing record must not raise into it."""
    from app.wiring.container import ObserveApprovalLedger

    ObserveApprovalLedger().record_decision(
        ctx, run_id="run_missing", tool_call_id="call_x", approved=False
    )


@pytest.mark.usefixtures("sync_session")
def test_a_recorded_request_can_be_read_back_from_the_task(db, ctx):
    """This is the point of the record: the task detail can find it."""
    from app.wiring.container import ObserveApprovalLedger

    ObserveApprovalLedger().record_pending(
        ctx,
        ApprovalRecord(
            run_id="run_1",
            task_id="tsk_1",
            thread_id=None,
            agent_id="agt_1",
            title="Approve tool call: plugin:pagerduty.page",
            policy_ref="tool_spec:plugin:pagerduty.page",
            tool_call_id="call_1",
            details={"tool_ref": "plugin:pagerduty.page"},
        ),
    )

    db.expire_all()
    rows = db.exec(select(ApprovalRequest).where(ApprovalRequest.task_id == "tsk_1")).all()
    assert len(rows) == 1
    assert rows[0].status == ApprovalStatus.PENDING.value
    assert rows[0].details_json["tool_call_id"] == "call_1"
