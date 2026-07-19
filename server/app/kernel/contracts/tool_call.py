"""Tool call contract types."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, cast


@dataclass(frozen=True)
class ToolCallRequest:
    """Stable input contract for invoking a tool."""

    id: str
    tool_ref: str
    arguments: dict[str, Any] = field(default_factory=dict[str, Any])
    run_id: str | None = None
    step_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCallRequest:
        """Deserialize from a JSON-compatible dict."""

        return cls(
            id=str(data.get("id") or ""),
            tool_ref=str(data.get("tool_ref") or ""),
            arguments=dict(data.get("arguments") or {}),
            run_id=data.get("run_id"),
            step_id=data.get("step_id"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class ToolCallError:
    """Stable error contract for failed tool calls."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCallError:
        """Deserialize from a JSON-compatible dict."""

        return cls(
            code=str(data.get("code") or ""),
            message=str(data.get("message") or ""),
            details=dict(data.get("details") or {}),
        )


@dataclass(frozen=True)
class ToolCallResult:
    """Stable output contract for tool invocation results."""

    id: str
    tool_ref: str
    success: bool
    result: Any = None
    error: ToolCallError | None = None
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCallResult:
        """Deserialize from a JSON-compatible dict."""

        error_data = data.get("error")
        return cls(
            id=str(data.get("id") or ""),
            tool_ref=str(data.get("tool_ref") or ""),
            success=bool(data.get("success")),
            result=data.get("result"),
            error=(
                ToolCallError.from_dict(cast(dict[str, Any], error_data))
                if isinstance(error_data, dict)
                else None
            ),
            metadata=dict(data.get("metadata") or {}),
        )


__all__ = ["ToolCallRequest", "ToolCallError", "ToolCallResult"]
