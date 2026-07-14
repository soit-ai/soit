"""Reference contracts for versioned runtime artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, TypeVar

TRef = TypeVar("TRef", bound="BaseRef")


@dataclass(frozen=True)
class BaseRef:
    """Parsed reference preserving the original wire value."""

    raw: str
    kind: str
    provider: str | None = None
    name: str | None = None
    version: str | None = None

    @classmethod
    def parse(cls: type[TRef], raw: str) -> TRef:
        """Parse refs shaped as kind:name, kind:provider:name, or kind:provider:name:version."""

        value = str(raw or "").strip()
        parts = value.split(":") if value else []
        kind = parts[0] if parts else cls.expected_kind()
        provider: str | None = None
        name: str | None = None
        version: str | None = None

        if len(parts) == 1:
            name = parts[0] if parts[0] != kind else None
        elif len(parts) == 2:
            name = parts[1]
        elif len(parts) == 3:
            provider = parts[1]
            name = parts[2]
        else:
            provider = parts[1]
            name = parts[2]
            version = ":".join(parts[3:])

        return cls(raw=value, kind=kind, provider=provider, name=name, version=version)

    @classmethod
    def expected_kind(cls) -> str:
        name = cls.__name__
        return name[:-3].lower() if name.endswith("Ref") else "ref"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""

        return asdict(self)

    @classmethod
    def from_dict(cls: type[TRef], data: dict[str, Any]) -> TRef:
        """Deserialize from a JSON-compatible dict."""

        return cls(
            raw=str(data.get("raw") or ""),
            kind=str(data.get("kind") or cls.expected_kind()),
            provider=data.get("provider"),
            name=data.get("name"),
            version=data.get("version"),
        )


@dataclass(frozen=True)
class ModelRef(BaseRef):
    """Reference to a model artifact."""


@dataclass(frozen=True)
class ToolRef(BaseRef):
    """Reference to a tool artifact."""


@dataclass(frozen=True)
class KnowledgeRef(BaseRef):
    """Reference to a knowledge artifact."""


@dataclass(frozen=True)
class PluginRef(BaseRef):
    """Reference to a plugin artifact."""


@dataclass(frozen=True)
class SecretRef(BaseRef):
    """Reference to a secret artifact."""


__all__ = [
    "BaseRef",
    "ModelRef",
    "ToolRef",
    "KnowledgeRef",
    "PluginRef",
    "SecretRef",
]
