"""Public application ports used by the Agent aggregate."""

from __future__ import annotations

from typing import Any, Protocol


class AgentCapabilityCatalogPort(Protocol):
    """Read cross-domain capabilities without exposing foreign ORM models."""

    def list_model_capabilities(self) -> list[dict[str, Any]]: ...

    def list_knowledge_capabilities(self) -> list[dict[str, Any]]: ...

    def list_workflow_capabilities(self) -> list[dict[str, Any]]: ...

    def list_plugin_capabilities(self) -> list[dict[str, Any]]: ...

    def resolve_skill_context(self, skill_refs: list[str]) -> str | None: ...

    def workflow_input_schema(self, workflow_ref: str) -> dict[str, Any]: ...

    def knowledge_runtime_defaults(self, knowledge_ref: str) -> dict[str, str]: ...


class EmptyAgentCapabilityCatalog:
    """Safe default for isolated application-service tests."""

    def list_model_capabilities(self) -> list[dict[str, Any]]:
        return []

    def list_knowledge_capabilities(self) -> list[dict[str, Any]]:
        return []

    def list_workflow_capabilities(self) -> list[dict[str, Any]]:
        return []

    def list_plugin_capabilities(self) -> list[dict[str, Any]]:
        return []

    def resolve_skill_context(self, skill_refs: list[str]) -> str | None:
        return None

    def workflow_input_schema(self, workflow_ref: str) -> dict[str, Any]:
        return {"type": "object", "additionalProperties": True}

    def knowledge_runtime_defaults(self, knowledge_ref: str) -> dict[str, str]:
        return {}
