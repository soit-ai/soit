""" spans

The span a governed call is traced under.

A failed call's exception can echo what the call was sent: a provider
repeating the prompt, a tool naming the URL it could not reach. Under
content-free capture the span records a failure by its label only, and still
ends as an error.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any

from opentelemetry.trace import Span, Status, StatusCode, Tracer

from app.kernel.commons.errors import KernelError


def failure_label(exc: BaseException) -> str:
    """What went wrong, without the message, which may echo input."""
    if isinstance(exc, KernelError):
        return exc.code
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        return f"status_{status_code}"
    return type(exc).__name__


@contextlib.contextmanager
def call_span(
    tracer: Tracer,
    name: str,
    *,
    attributes: dict[str, Any],
    keeps_content: bool,
) -> Iterator[Span]:
    """A current span for one governed call."""
    with tracer.start_as_current_span(
        name,
        attributes=attributes,
        record_exception=keeps_content,
        set_status_on_exception=keeps_content,
    ) as span:
        try:
            yield span
        except Exception as exc:
            if not keeps_content:
                span.set_status(Status(StatusCode.ERROR, failure_label(exc)))
            raise
