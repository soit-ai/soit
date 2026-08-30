"""test_egress_block_recording

A refused outbound request must leave evidence, not just an exception. These
cover the recorder hook on the policy's deny paths and the windowed summary the
governance panel reads.
"""

from datetime import timedelta

import pytest

from app.kernel.commons.errors import ForbiddenError
from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.security.egress import (
    EGRESS_BLOCK_EVENT_TYPE,
    check_egress_policy,
    record_egress_block,
    register_egress_block_recorder,
    reset_egress_block_recorder,
)
from app.modules.security.application.service import SecurityService
from app.settings.settings import settings


class _RecordingSink:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def record_block(self, ctx, *, resource_ref, url, domain, reason, bundles=None) -> None:
        self.calls.append(
            {
                "tenant_id": ctx.tenant_id,
                "resource_ref": resource_ref,
                "url": url,
                "domain": domain,
                "reason": reason,
                "bundles": bundles,
            }
        )


class _ExplodingSink:
    def record_block(self, ctx, **kwargs) -> None:
        raise RuntimeError("sink is down")


@pytest.fixture
def egress_enabled():
    previous = settings.enable_egress_policy
    settings.enable_egress_policy = True
    try:
        yield
    finally:
        settings.enable_egress_policy = previous
        reset_egress_block_recorder()


@pytest.mark.usefixtures("egress_enabled")
def test_a_request_outside_the_allowlist_is_recorded(ctx):
    sink = _RecordingSink()
    register_egress_block_recorder(sink)

    with pytest.raises(ForbiddenError):
        check_egress_policy(ctx, "tool:http.fetch", {"url": "https://not-allowed.example/x"})

    assert len(sink.calls) == 1
    assert sink.calls[0]["domain"] == "not-allowed.example"
    assert sink.calls[0]["resource_ref"] == "tool:http.fetch"
    assert sink.calls[0]["reason"] == "not_allowlisted"


@pytest.mark.usefixtures("egress_enabled")
def test_a_failing_recorder_never_turns_a_refusal_into_a_crash(ctx):
    """The policy already decided; losing the evidence must not change that."""
    register_egress_block_recorder(_ExplodingSink())

    with pytest.raises(ForbiddenError):
        check_egress_policy(ctx, "tool:http.fetch", {"url": "https://not-allowed.example/x"})


def test_recording_without_a_registered_sink_is_a_no_op(ctx):
    reset_egress_block_recorder()
    record_egress_block(
        ctx,
        resource_ref="tool:http.fetch",
        url="https://example.com",
        domain="example.com",
        reason="not_allowlisted",
    )


def test_the_summary_counts_blocks_and_names_who_was_refused(db, ctx):
    now = utc_now()
    for age_hours, resource_ref, domain in (
        (1, "agent:agt_a", "paste.example"),
        (2, "agent:agt_a", "paste.example"),
        (2, "agent:agt_b", "other.example"),
        (48, "agent:agt_c", "old.example"),
    ):
        db.add(
            AuditEvent(
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                event_type=EGRESS_BLOCK_EVENT_TYPE,
                resource_type="egress",
                resource_id=domain,
                operation="egress",
                outcome="denied",
                created_at=now - timedelta(hours=age_hours),
                payload_json={"resource_ref": resource_ref, "reason": "not_allowlisted"},
            )
        )
    db.commit()

    service = SecurityService(db, ctx, identity_policy_scope=None)
    summary = service.summarize_egress_blocks(since=now - timedelta(hours=24))

    assert summary.total == 3
    assert summary.subjects == 2
    assert summary.domains == 2
    assert summary.recent[0].domain in {"paste.example", "other.example"}


def test_policy_change_audits_are_not_counted_as_blocks(db, ctx):
    """/egress/audits records changes to the policy; blocks are a different fact."""
    db.add(
        AuditEvent(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            event_type="security.egress_policy.updated",
            resource_type="egress_policy",
            operation="update",
            scope="workspace",
        )
    )
    db.commit()

    service = SecurityService(db, ctx, identity_policy_scope=None)
    assert service.summarize_egress_blocks().total == 0


@pytest.mark.usefixtures("egress_enabled")
def test_a_refusal_cites_the_policy_that_refused_it(ctx):
    """Rules move on; a refusal has to stay readable after they do."""
    from app.kernel.security.egress import (
        EgressScopePolicy,
        register_egress_scope_policy_provider,
        reset_egress_scope_policy_provider,
    )

    class _Provider:
        def get_scope_policy(self, ctx):
            return EgressScopePolicy(
                workspace_blocklist=["paste.example"],
                tenant_bundle_id="pb_tenant",
                workspace_bundle_id="pb_workspace",
            )

    sink = _RecordingSink()
    register_egress_block_recorder(sink)
    register_egress_scope_policy_provider(_Provider())
    try:
        with pytest.raises(ForbiddenError):
            check_egress_policy(ctx, "tool:http.fetch", {"url": "https://paste.example/x"})
    finally:
        reset_egress_scope_policy_provider()

    assert sink.calls[0]["reason"] == "workspace_blocklist"
    assert sink.calls[0]["bundles"] == {
        "tenant_bundle_id": "pb_tenant",
        "workspace_bundle_id": "pb_workspace",
    }


@pytest.mark.usefixtures("egress_enabled")
def test_a_refusal_decided_without_a_scope_policy_cites_nothing(ctx):
    """Naming an identifier that does not exist would be worse than silence."""
    sink = _RecordingSink()
    register_egress_block_recorder(sink)

    with pytest.raises(ForbiddenError):
        check_egress_policy(ctx, "tool:http.fetch", {"url": "https://not-allowed.example/x"})

    assert sink.calls[0]["bundles"] == {
        "tenant_bundle_id": None,
        "workspace_bundle_id": None,
    }


def test_the_summary_carries_the_bundle_that_refused_each_request(db, ctx):
    db.add(
        AuditEvent(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            event_type=EGRESS_BLOCK_EVENT_TYPE,
            resource_type="egress",
            resource_id="paste.example",
            operation="egress",
            outcome="denied",
            payload_json={
                "resource_ref": "agent:agt_a",
                "reason": "workspace_blocklist",
                "workspace_bundle_id": "pb_workspace",
            },
        )
    )
    db.commit()

    service = SecurityService(db, ctx, identity_policy_scope=None)
    summary = service.summarize_egress_blocks()

    assert summary.recent[0].workspace_bundle_id == "pb_workspace"
    assert summary.recent[0].tenant_bundle_id is None
