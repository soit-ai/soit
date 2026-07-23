"""Secret resolution and trusted value-store interfaces."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.kernel.commons.errors import ValidationError

_OPAQUE_SECRET_ID = re.compile(r"^sec_[A-Za-z0-9][A-Za-z0-9_-]{2,124}$")


def require_opaque_secret_id(secret_id: str) -> str:
    """Validate a public/runtime secret identifier and reject storage locators."""
    normalized = str(secret_id or "").strip()
    if not _OPAQUE_SECRET_ID.fullmatch(normalized):
        raise ValidationError("Secret resolution requires an opaque secret_id")
    return normalized


@dataclass(frozen=True, slots=True)
class SecretLocator:
    """Trusted storage locator created only after scoped metadata resolution."""

    value: str


class SecretsPort(ABC):
    """Runtime secret resolver that accepts opaque secret identifiers only."""

    @abstractmethod
    async def get_secret(self, secret_id: str, **kwargs: Any) -> str:
        """Resolve a scoped secret value by its opaque identifier."""
        raise NotImplementedError


class SecretValueStore(ABC):
    """Low-level secret storage available only to trusted application services."""

    @abstractmethod
    async def get_secret_value(
        self,
        locator: SecretLocator,
        **kwargs: Any,
    ) -> str:
        """Read a value from a trusted storage locator."""
        raise NotImplementedError

    @abstractmethod
    async def set_secret_value(
        self,
        locator: SecretLocator,
        value: str,
        **kwargs: Any,
    ) -> None:
        """Write a value to a trusted storage locator."""
        raise NotImplementedError

    @abstractmethod
    async def delete_secret_value(
        self,
        locator: SecretLocator,
        **kwargs: Any,
    ) -> None:
        """Delete a value at a trusted storage locator."""
        raise NotImplementedError
