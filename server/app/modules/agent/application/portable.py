"""An agent as a file: what ``soit agent export`` writes and ``soit agent import`` reads.

The file names the agent (name, description, visibility, category, tags) and
carries one version's specification in the shape a new version is created
from, so importing it goes through the same validation and binding resolution
as creating a version by hand. Ids are left out on purpose: the file moves an
agent between workspaces and into version control, where ids mean nothing.
The bindings it names (a model ref, tool refs, knowledge refs) must exist in
the importing workspace, or the import is refused as a version creation
would be.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.agent.application.schemas import (
    AgentCapabilityBindings,
    AgentCreate,
    AgentResponse,
    AgentVersionCreate,
    AgentVersionResponse,
)

AGENT_FILE_FORMAT = "agent/v1"


class AgentFileAgent(BaseModel):
    """The agent's own fields, without ids, ownership or counters."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=2000)
    visibility: str = Field(default="private", pattern="^(private|workspace|tenant|public)$")
    category: str | None = Field(default=None, max_length=128)
    icon_url: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = None

    def as_create(self) -> AgentCreate:
        return AgentCreate(
            name=self.name,
            description=self.description,
            visibility=self.visibility,
            category=self.category,
            icon_url=self.icon_url,
            tags=self.tags,
        )


class AgentFile(BaseModel):
    """The portable document; ``soit`` names its format."""

    model_config = ConfigDict(extra="forbid")

    soit: Literal["agent/v1"] = AGENT_FILE_FORMAT
    agent: AgentFileAgent
    version: AgentVersionCreate | None = None
    """The exported version's specification; None for an agent with no version yet."""


class AgentImportResponse(BaseModel):
    agent: AgentResponse
    version: AgentVersionResponse | None = None


def version_create_from_spec(spec: dict[str, Any]) -> AgentVersionCreate:
    """The creation payload that builds ``spec``: the inverse of the version spec builder.

    A stored spec carries the same values under the runtime's names (``limits``,
    ``policies``, ``memory``); read back into the creation shape, a re-created
    version has the same checksum as the exported one.
    """
    bindings = spec.get("bindings") or {}
    limits = spec.get("limits") or {}
    policies = spec.get("policies") or {}
    memory = spec.get("memory") or {}
    memory_policy = memory.get("policy") or {}
    timeout_ms = limits.get("timeout_ms")
    return AgentVersionCreate(
        system_prompt=spec.get("system_prompt"),
        temperature=spec.get("temperature"),
        max_iterations=limits.get("max_iterations"),
        max_tool_calls=limits.get("max_tool_calls"),
        max_llm_calls=limits.get("max_llm_calls"),
        max_failures=limits.get("max_failures"),
        max_runtime_seconds=int(timeout_ms) // 1000 if timeout_ms else None,
        max_tokens_total=limits.get("max_tokens"),
        max_cost=limits.get("budget"),
        cost_currency=policies.get("cost_currency"),
        rag_top_k=limits.get("rag_top_k"),
        rag_strategy=policies.get("rag_strategy"),
        context_window_messages=limits.get("context_window_messages"),
        context_window_chars=limits.get("context_window_chars"),
        bindings=AgentCapabilityBindings(
            model_ref=bindings.get("model_ref") or "",
            knowledge_refs=list(bindings.get("knowledge_refs") or []),
            tool_refs=list(bindings.get("tool_refs") or []),
            workflow_refs=list(bindings.get("workflow_refs") or []),
            skill_refs=list(bindings.get("skill_refs") or []),
        ),
        memory_strategy=memory.get("type"),
        memory_top_k=memory_policy.get("top_k"),
        verify=policies.get("verify"),
        failure_strategy=policies.get("failure_strategy"),
    )
