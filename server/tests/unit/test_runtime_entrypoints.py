"""Tests for runtime service entrypoint wiring after kernel migration."""

from app.api.v1.agent.thread_dependencies import (
    get_thread_query_service,
    get_thread_runtime_service,
)
from app.api.v1.responses.dependencies import (
    get_response_projection_coordinator,
    get_response_service,
)
from app.api.v1.run.dependencies import get_run_service
from app.api.v1.task.dependencies import get_task_runtime_service, get_task_service
from app.kernel.runtime.responses.orchestrator import ResponseProjectionCoordinator
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.service import RunService
from app.kernel.runtime.tasks.query_service import TaskQueryService
from app.kernel.runtime.tasks.service import TaskService
from app.kernel.runtime.threads.service import ThreadService
from app.modules.agent.application.thread_query_service import AgentThreadQueryService
from app.wiring import services as service_wiring


class FakeContainer:
    def get_event_bus(self):
        return None

    def get_llm_port(self, **_kwargs):
        return object()

    def get_storage_port(self, **_kwargs):
        return object()


def test_task_api_dependencies_use_runtime_task_services(db, ctx):
    assert isinstance(get_task_service(ctx=ctx, db=db), TaskQueryService)
    assert isinstance(get_task_runtime_service(ctx=ctx, db=db), TaskService)


def test_thread_api_dependencies_use_runtime_thread_service(db, ctx):
    assert isinstance(get_thread_query_service(ctx=ctx, db=db), AgentThreadQueryService)
    assert isinstance(get_thread_runtime_service(ctx=ctx, db=db), ThreadService)


def test_run_api_dependency_uses_runtime_run_service(db, ctx):
    assert isinstance(get_run_service(ctx=ctx, db=db), RunService)


def test_response_api_dependencies_use_runtime_response_services(db, ctx, monkeypatch):
    monkeypatch.setattr(service_wiring, "get_container", lambda: FakeContainer())

    response_service = get_response_service(ctx=ctx, db=db)
    projection_coordinator = get_response_projection_coordinator(ctx=ctx, db=db)

    assert isinstance(response_service, ResponseService)
    assert isinstance(projection_coordinator, ResponseProjectionCoordinator)
    assert isinstance(projection_coordinator.thread_service, ThreadService)
