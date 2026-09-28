"""The models a caller can name, for entry points that list them.

The gateway's ``/v1/models`` lists them without reaching into the model hub
module: the composition root provides an implementation of this port.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class CallableModel:
    id: str
    """The ref a call names: ``model:{slug}:{model_id}`` or ``vmodel:{slug}``."""
    created_at: datetime
    owned_by: str


class ModelCatalogPort(Protocol):
    async def list_callable_models(self) -> list[CallableModel]:
        """Active models of active providers, then active virtual models."""
        ...
