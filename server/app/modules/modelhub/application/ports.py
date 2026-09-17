""" ports

Protocols (ports) for modelhub application layer.
Application code depends on these protocols, not infra implementations.
"""

from __future__ import annotations

from typing import Any, Protocol


class ModelRepositoryPort(Protocol):
    async def get_by_name(self, *args: Any, **kwargs: Any) -> Any: ...
    async def get_by_model_ref(self, *args: Any, **kwargs: Any) -> Any: ...
    async def list(self, *args: Any, **kwargs: Any) -> Any: ...


class ModelReferenceUsagePort(Protocol):
    """Find active product configuration that references a canonical model ref."""

    async def list_references(self, model_ref: str) -> list[dict[str, str]]: ...
