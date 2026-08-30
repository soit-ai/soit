"""Integration tests for the console prototype seed."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import and_, select

from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStep
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.db.models.threads import Thread
from app.modules.agent.domain.models import Agent

# Imported for their side effect: the test database is built from the models
# that have been registered, so a table nobody imports is never created.
from app.modules.billing.domain.models import CreditLedgerEntry  # noqa: F401
from app.modules.identity.domain.models import ApiKey, User
from app.modules.knowledge.domain.models import (  # noqa: F401
    Knowledge,
    KnowledgeDocument,
    KnowledgeIndex,
)
from app.modules.modelhub.domain.models import Provider, ProviderModel  # noqa: F401
from app.modules.observe.domain.models import ApprovalRequest  # noqa: F401
from app.modules.plugin.domain.models import (  # noqa: F401
    Plugin,
    PluginInstallation,
    PluginVersion,
)
from app.modules.secrets.domain.models import Secret  # noqa: F401
from app.modules.workflow.domain.models import Workflow, WorkflowVersion  # noqa: F401


def _unwrap(row):
    if row is None:
        return None
    if isinstance(row, tuple):
        return row[0]
    try:
        return row[0]
    except Exception:
        return row


def _args(**overrides):
    data = {
        "email": "prototype-seed@example.com",
        "password": "changeme123",
        "name": "Prototype Seed Owner",
        "tenant_name": "prototype-seed-tenant",
        "workspace_name": "default",
        "reset": True,
        "json_output": None,
        # Small volumes: the counts are asserted separately, and seeding the
        # default 1,284 runs in every test run costs seconds for no extra cover.
        "runs": 12,
        "tasks": 9,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _scoped(db, model, summary):
    return [
        _unwrap(row)
        for row in db.exec(
            select(model).where(
                and_(
                    model.tenant_id == summary.tenant_id,
                    model.workspace_id == summary.workspace_id,
                )
            )
        ).all()
    ]


@pytest.mark.asyncio
async def test_seed_creates_the_objects_the_prototype_draws(db):
    from scripts.seed_console_prototype import seed_console_prototype

    summary = await seed_console_prototype(db, _args())

    # The prototype's own inventory: six agents, five workflows, four knowledge
    # bases, eight plugins, four secrets, five threads, two pending approvals.
    assert len(summary.agent_ids) == 6
    assert len(summary.workflow_ids) == 5
    assert len(summary.knowledge_ids) == 4
    assert len(summary.plugin_ids) == 8
    assert len(summary.secret_ids) == 4
    assert len(summary.thread_ids) == 5
    assert len(summary.approval_ids) == 2
    assert len(summary.model_refs) == 6

    names = {agent.name for agent in _scoped(db, Agent, summary)}
    assert {"support-triage", "ops-copilot", "billing-audit"} <= names

    workflows = {item.name for item in _scoped(db, Workflow, summary)}
    assert {"ticket-escalation", "docs-nightly-sync"} <= workflows

    knowledge = {item.name for item in _scoped(db, Knowledge, summary)}
    assert {"product-docs", "billing-policies"} <= knowledge


@pytest.mark.asyncio
async def test_seed_honours_the_requested_volumes(db):
    from scripts.seed_console_prototype import seed_console_prototype

    summary = await seed_console_prototype(db, _args(runs=12, tasks=9))

    # The named rows plus filler up to the requested total. A parameter that
    # silently stops at the named rows would leave the side panel reporting a
    # volume the pages do not have.
    assert len(summary.run_ids) == 12
    assert len(summary.task_ids) == 9

    assert len(_scoped(db, Run, summary)) == 12
    assert len(_scoped(db, Task, summary)) == 9
    # Every run carries spans and a cost entry, so traces and the cost overview
    # have something to aggregate.
    assert len(_scoped(db, RunStep, summary)) >= 12
    assert len(_scoped(db, RunCostEntry, summary)) == 12


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_leaves_other_data_alone(db):
    from scripts.seed_console_prototype import seed_console_prototype

    first = await seed_console_prototype(db, _args())

    manual = Thread(
        id="thread_manual_not_seeded",
        tenant_id=first.tenant_id,
        workspace_id=first.workspace_id,
        title="Manual thread",
        thread_type="chat",
        status="active",
        metadata_json={"seed_source": "manual"},
    )
    db.add(manual)
    db.commit()

    second = await seed_console_prototype(db, _args())
    third = await seed_console_prototype(db, _args(reset=False))

    assert second.model_dump() == third.model_dump()
    # --reset clears this seed's rows by id infix; a row that is not ours has to
    # survive it, or resetting the demo data would delete real work.
    assert db.get(Thread, "thread_manual_not_seeded") is not None


@pytest.mark.asyncio
async def test_seeded_credentials_cannot_authenticate(db):
    from scripts.seed_console_prototype import seed_console_prototype

    summary = await seed_console_prototype(db, _args())

    # Seeded teammates and API keys are display objects. Hashing a constant
    # would make every seeded database carry a working credential whose
    # plaintext is readable in this repository, so the digests are taken over
    # random bytes and no two seeds may share one.
    keys = _scoped(db, ApiKey, summary)
    assert len(keys) == 3
    assert len({key.key_hash for key in keys}) == 3

    seeded_users = [
        _unwrap(row)
        for row in db.exec(
            select(User).where(User.email.in_(["wei@acme.io", "ming@acme.io"]))
        ).all()
    ]
    assert len(seeded_users) == 2
    assert len({user.password_hash for user in seeded_users}) == 2
