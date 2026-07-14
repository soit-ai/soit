"""Tests for centralized runtime SQLModel model registration."""

from sqlmodel import SQLModel

from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.events import EventConsumerCheckpoint, EventOutbox
from app.kernel.runtime.db.models.observe import IdempotencyKey
from app.kernel.runtime.db.models.responses import Response, ResponseEvent
from app.kernel.runtime.db.models.runs import Run, RunArtifact, RunCostEntry, RunStep
from app.kernel.runtime.db.models.tasks import Task, TaskCheckpoint, TaskEvent
from app.kernel.runtime.db.models.threads import Thread, ThreadMessage


def test_runtime_db_models_package_registers_all_kernel_runtime_tables():
    import app.kernel.runtime.db.models  # noqa: F401

    expected_tables = {
        "audit_events",
        "event_outbox",
        "event_consumer_checkpoint",
        "idempotency_keys",
        "responses",
        "response_events",
        "runs",
        "run_steps",
        "run_artifacts",
        "run_cost_entries",
        "tasks",
        "task_checkpoints",
        "task_events",
        "threads",
        "thread_messages",
    }

    assert expected_tables.issubset(set(SQLModel.metadata.tables))


def test_kernel_runtime_table_classes_live_under_runtime_db_models():
    table_classes = [
        AuditEvent,
        EventConsumerCheckpoint,
        EventOutbox,
        IdempotencyKey,
        Response,
        ResponseEvent,
        Run,
        RunArtifact,
        RunCostEntry,
        RunStep,
        Task,
        TaskCheckpoint,
        TaskEvent,
        Thread,
        ThreadMessage,
    ]

    assert {
        table_class.__module__
        for table_class in table_classes
        if not table_class.__module__.startswith("app.kernel.runtime.db.models.")
    } == set()
