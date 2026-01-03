""" ports

Protocols (ports) for workflow application layer.
Application code depends on these protocols, not infra implementations.
"""

from __future__ import annotations

from typing import Protocol, Any, Optional, Sequence

class WorkflowRepositoryPort(Protocol):
    def get_by_name(self, *args: Any, **kwargs: Any) -> Any: ...
    def get_current_version(self, *args: Any, **kwargs: Any) -> Any: ...
    def list_versions(self, *args: Any, **kwargs: Any) -> Any: ...

class WorkflowVersionRepositoryPort(Protocol):
    ...
