"""Vector query/result contract types."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, cast


@dataclass(frozen=True)
class VectorDocument:
    """A document stored in or returned from a vector index."""

    id: str
    text: str | None = None
    vector: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VectorDocument:
        """Deserialize from a JSON-compatible dict."""

        vector = data.get("vector")
        return cls(
            id=str(data.get("id") or ""),
            text=data.get("text"),
            vector=list(cast(list[float], vector)) if isinstance(vector, list) else None,
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class VectorQuery:
    """Stable vector search query contract."""

    collection: str
    vector: list[float]
    top_k: int = 10
    filter: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VectorQuery:
        """Deserialize from a JSON-compatible dict."""

        return cls(
            collection=str(data.get("collection") or ""),
            vector=list(cast(list[float], data.get("vector") or [])),
            top_k=int(data.get("top_k") or 10),
            filter=dict(data["filter"]) if isinstance(data.get("filter"), dict) else None,
        )


@dataclass(frozen=True)
class VectorQueryMatch:
    """Stable vector search match contract."""

    document: VectorDocument
    score: float
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VectorQueryMatch:
        """Deserialize from a JSON-compatible dict."""

        document: Any = data.get("document") or {}
        return cls(
            document=(
                VectorDocument.from_dict(cast(dict[str, Any], document))
                if isinstance(document, dict)
                else cast(VectorDocument, document)
            ),
            score=float(data.get("score") or 0),
            metadata=dict(data.get("metadata") or {}),
        )


__all__ = ["VectorDocument", "VectorQuery", "VectorQueryMatch"]
