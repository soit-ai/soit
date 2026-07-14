"""context

Contextvars for request/run logging.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_tenant_id: ContextVar[str | None] = ContextVar("tenant_id", default=None)
_workspace_id: ContextVar[str | None] = ContextVar("workspace_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)
_run_id: ContextVar[str | None] = ContextVar("run_id", default=None)
_step_id: ContextVar[str | None] = ContextVar("step_id", default=None)


def set_request_context(
    *,
    request_id: str | None = None,
    trace_id: str | None = None,
    tenant_id: str | None = None,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """Bind request-level context to the current task."""
    if request_id is not None:
        _request_id.set(request_id)
    if trace_id is not None:
        _trace_id.set(trace_id)
    if tenant_id is not None:
        _tenant_id.set(tenant_id)
    if workspace_id is not None:
        _workspace_id.set(workspace_id)
    if user_id is not None:
        _user_id.set(user_id)


def set_run_context(run_id: str | None) -> None:
    """Bind run_id to the current task."""
    if run_id is not None:
        _run_id.set(run_id)


def set_step_context(step_id: str | None) -> None:
    """Bind step_id to the current task."""
    if step_id is not None:
        _step_id.set(step_id)


def clear_request_context() -> None:
    """Clear request-level context."""
    _request_id.set(None)
    _trace_id.set(None)
    _tenant_id.set(None)
    _workspace_id.set(None)
    _user_id.set(None)


def clear_run_context() -> None:
    """Clear run_id context."""
    _run_id.set(None)


def clear_step_context() -> None:
    """Clear step_id context."""
    _step_id.set(None)


def get_log_context() -> dict[str, Any]:
    """Return current logging context fields."""
    return {
        "request_id": _request_id.get(),
        "trace_id": _trace_id.get(),
        "tenant_id": _tenant_id.get(),
        "workspace_id": _workspace_id.get(),
        "user_id": _user_id.get(),
        "run_id": _run_id.get(),
        "step_id": _step_id.get(),
    }
