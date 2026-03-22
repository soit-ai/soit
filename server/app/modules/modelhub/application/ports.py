""" ports

Protocols (ports) for modelhub application layer.
Application code depends on these protocols, not infra implementations.
"""

from __future__ import annotations

from typing import Protocol, Any, Optional, Sequence

class ModelRepositoryPort(Protocol):
    def get_by_name(self, *args: Any, **kwargs: Any) -> Any: ...
    def get_by_model_ref(self, *args: Any, **kwargs: Any) -> Any: ...
    def list(self, *args: Any, **kwargs: Any) -> Any: ...
