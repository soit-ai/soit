"""Public workflow application contracts for other product modules."""

from __future__ import annotations

from typing import Protocol


class PublishedWorkflowUsagePort(Protocol):
    """Read published workflow specifications without exposing workflow ORM models."""

    def list_published_specs(self) -> list[dict]: ...
