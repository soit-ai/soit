"""Agent aggregate application service."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.guard import rbac_guard, workspace_guard
from app.kernel.identity.permissions import RESOURCE_AGENT
from app.kernel.ports.llm.interface import LLMPort
from app.kernel.ports.tools.interface import ToolPort
from app.kernel.responses.repository import ResponseEventRepository, ResponseRepository
from app.kernel.responses.service import ResponseService
from app.kernel.runtime.contracts.status import TaskStatus
from app.kernel.runtime.core.service import RuntimeCoreService
from app.kernel.specs.validator import validate_runtime_spec
from app.kernel.trace.writer import TraceWriter
from app.modules.agent.application.schemas import (
    AgentCapabilityBindings,
    AgentCreate,
    AgentRunRequest,
    AgentUpdate,
    AgentVersionCreate,
)
from app.adapters.tools.resolver import ToolResolver
from app.modules.agent.application.service import AgentService
from app.modules.agent.application.versioning_adapter import AgentVersioningAdapter
from app.modules.agent.domain.models import Agent, AgentBinding, AgentVersion
from app.modules.agent.infra.repository import (
    AgentBindingRepository,
    AgentPublishRepository,
    AgentRepository,
    AgentVersionRepository,
)
from app.modules.memory.application.service import MemoryService
from app.modules.versioning.application.service import VersionControlService


class AgentApplicationService:
    """Agent CRUD, publish, and execution service backed by Agent tables."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        *,
        llm_port: LLMPort,
        tool_port: ToolPort,
        memory_service: Optional[MemoryService] = None,
        trace_writer: Optional[TraceWriter] = None,
        response_service: Optional[ResponseService] = None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.llm_port = llm_port
        self.tool_port = tool_port
        self.memory_service = memory_service
        # Create ToolResolver if tool_port is a RegistryToolRouterPort
        from app.adapters.tools.router import RegistryToolRouterPort
        self.tool_resolver = ToolResolver(tool_port=tool_port) if isinstance(tool_port, RegistryToolRouterPort) else None
        self.trace_writer = trace_writer or TraceWriter(db, ctx)
        self.response_service = response_service or ResponseService(
            db=db,
            ctx=ctx,
            response_repo=ResponseRepository(db, ctx),
            event_repo=ResponseEventRepository(db, ctx),
            trace_writer=self.trace_writer,
        )
        self.agent_repo = AgentRepository(db, ctx)
        self.version_repo = AgentVersionRepository(db, ctx)
        self.binding_repo = AgentBindingRepository(db, ctx)
        self.publish_repo = AgentPublishRepository(db, ctx)
        self.runtime_core = RuntimeCoreService(db, ctx)
        self.versioning = VersionControlService(
            AgentVersioningAdapter(
                agent_repo=self.agent_repo,
                version_repo=self.version_repo,
                publish_repo=self.publish_repo,
                sync_bindings=self._sync_bindings,
            )
        )

    def _resolve_agent_create_id(self, data: AgentCreate, **kwargs) -> str:
        return data.name or f"new:{self.ctx.workspace_id}"

    def _get_agent(self, agent_id: str) -> Agent:
        agent = self.agent_repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundError(f"Agent not found: {agent_id}")
        return agent

    def _get_version(self, version_id: str) -> AgentVersion:
        version = self.version_repo.get_by_id(version_id)
        if not version:
            raise NotFoundError(f"Version not found: {version_id}")
        return version

    def _resolve_execution_version(self, agent: Agent) -> AgentVersion:
        version_id = agent.published_version_id
        if not version_id:
            raise ValidationError(f"Agent has no published version to execute: {agent.id}")
        version = self._get_version(version_id)
        if version.agent_id != agent.id:
            raise ValidationError(f"Version {version.id} does not belong to agent {agent.id}")
        return version

    def _merge_ref_lists(self, *groups: Optional[List[str]]) -> List[str]:
        seen: set[str] = set()
        merged: List[str] = []
        for group in groups:
            for value in group or []:
                if not value or value in seen:
                    continue
                seen.add(value)
                merged.append(value)
        return merged

    def _resolve_version_bindings(self, data: AgentVersionCreate) -> AgentCapabilityBindings:
        explicit = data.bindings or AgentCapabilityBindings()
        model_ref = explicit.model_ref or data.model_ref
        # Merge deprecated plugin_refs into tool_refs
        merged_tool_refs = self._merge_ref_lists(
            explicit.tool_refs, data.tool_refs,
            explicit.plugin_refs, data.plugin_refs,
        )
        return AgentCapabilityBindings(
            model_ref=model_ref,
            knowledge_refs=self._merge_ref_lists(explicit.knowledge_refs, data.knowledge_refs),
            tool_refs=merged_tool_refs or None,
            workflow_refs=self._merge_ref_lists(explicit.workflow_refs, data.workflow_refs),
            skill_refs=self._merge_ref_lists(explicit.skill_refs, data.skill_refs),
            plugin_refs=self._merge_ref_lists(explicit.plugin_refs, data.plugin_refs) or None,
        )

    def _build_spec(
        self,
        data: AgentVersionCreate,
        bindings: Optional[AgentCapabilityBindings] = None,
    ) -> Dict[str, Any]:
        bindings = bindings or self._resolve_version_bindings(data)
        memory_enabled = data.memory_strategy is not None or data.memory_top_k is not None
        memory_policy: Dict[str, Any] = {}
        if data.memory_top_k is not None:
            memory_policy["top_k"] = data.memory_top_k
        knowledge_refs = [item for item in (bindings.knowledge_refs or []) if item]
        tool_refs = [item for item in (bindings.tool_refs or []) if item]
        limits: Dict[str, Any] = {
            "max_iterations": data.max_iterations,
            "max_tool_calls": data.max_tool_calls,
            "max_llm_calls": data.max_llm_calls,
            "max_failures": data.max_failures,
            "timeout_ms": data.max_runtime_seconds * 1000 if data.max_runtime_seconds else None,
            "max_tokens": data.max_tokens_total,
            "budget": data.max_cost,
        }
        policies = {
            "verify": data.verify,
            "failure_strategy": data.failure_strategy,
            "cost_currency": data.cost_currency,
        }
        return {
            "runtime": "agent_runtime_v1",
            "planner": None,
            "system_prompt": data.system_prompt,
            "model": {
                "ref_key": bindings.model_ref,
                "params": {"temperature": data.temperature} if data.temperature is not None else {},
            },
            "tools": {
                "allowlist": tool_refs or None,
                "configs": None,
            },
            "bindings": {
                "model_ref": bindings.model_ref,
                "knowledge_refs": knowledge_refs or None,
                "tool_refs": (bindings.tool_refs or None),
                "workflow_refs": bindings.workflow_refs or None,
                "skill_refs": bindings.skill_refs or None,
                "plugin_refs": bindings.plugin_refs or None,
            },
            "memory": {
                "enabled": memory_enabled or None,
                "type": data.memory_strategy,
                "policy": memory_policy or None,
            },
            "rag": {"knowledges": knowledge_refs} if knowledge_refs else None,
            "limits": limits,
            "policies": policies,
        }

    def _build_checksum(self, spec: Dict[str, Any]) -> str:
        payload = json.dumps(spec, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _sync_bindings(
        self,
        agent: Agent,
        version: AgentVersion,
    ) -> None:
        spec = version.spec_json or {}
        binding_spec = spec.get("bindings") or {}
        model_ref = binding_spec.get("model_ref") or ((spec.get("model") or {}).get("ref_key") if isinstance(spec.get("model"), dict) else None)
        bindings_to_create: List[AgentBinding] = []

        if model_ref:
            bindings_to_create.append(
                AgentBinding(
                    agent_id=agent.id,
                    agent_version_id=version.id,
                    binding_type="model",
                    target_key=model_ref,
                    config_json={},
                )
            )

        binding_groups = [
            ("tool", binding_spec.get("tool_refs") or (spec.get("tools") or {}).get("allowlist") or []),
            ("knowledge", binding_spec.get("knowledge_refs") or (spec.get("rag") or {}).get("knowledges") or []),
            ("workflow", binding_spec.get("workflow_refs") or []),
            ("skill", binding_spec.get("skill_refs") or []),
            ("plugin", binding_spec.get("plugin_refs") or []),
        ]
        for binding_type, values in binding_groups:
            for sort_order, target_key in enumerate(values):
                if not target_key:
                    continue
                bindings_to_create.append(
                    AgentBinding(
                        agent_id=agent.id,
                        agent_version_id=version.id,
                        binding_type=binding_type,
                        target_key=target_key,
                        config_json={},
                        sort_order=sort_order,
                    )
                )

        if bindings_to_create:
            self.binding_repo.create_many(bindings_to_create)

    def _request_from_version(self, version: AgentVersion, inputs: Dict[str, Any]) -> AgentRunRequest:
        spec = version.spec_json or {}
        model_spec = spec.get("model") or {}
        model_params = model_spec.get("params") or {} if isinstance(model_spec, dict) else {}
        tool_refs = (spec.get("tools") or {}).get("allowlist")
        memory_spec = spec.get("memory") or {}
        memory_policy = memory_spec.get("policy") or {} if isinstance(memory_spec, dict) else {}
        limits = spec.get("limits") or {}
        policies = spec.get("policies") or {}

        messages = list(inputs.get("messages") or [])
        system_prompt = spec.get("system_prompt")
        if system_prompt and not any(message.get("role") == "system" for message in messages):
            messages = [{"role": "system", "content": system_prompt}] + messages

        payload = {
            "messages": messages,
            "model": inputs.get("model") or model_spec.get("ref_key"),
            "temperature": inputs.get("temperature", model_params.get("temperature")),
            "max_iterations": inputs.get("max_iterations", limits.get("max_iterations") or 8),
            "max_tool_calls": inputs.get("max_tool_calls", limits.get("max_tool_calls") or 8),
            "max_llm_calls": inputs.get("max_llm_calls", limits.get("max_llm_calls") or 16),
            "max_failures": inputs.get("max_failures", limits.get("max_failures") or 2),
            "max_runtime_seconds": inputs.get(
                "max_runtime_seconds",
                int(limits["timeout_ms"] / 1000) if limits.get("timeout_ms") else None,
            ),
            "max_tokens_total": inputs.get("max_tokens_total", limits.get("max_tokens")),
            "max_cost": inputs.get("max_cost", limits.get("budget")),
            "cost_currency": inputs.get("cost_currency", policies.get("cost_currency") or "USD"),
            "tool_refs": inputs.get("tool_refs", tool_refs),
            "knowledge_refs": inputs.get("knowledge_refs", (spec.get("rag") or {}).get("knowledges")),
            "rag_top_k": inputs.get("rag_top_k", 5),
            "rag_strategy": inputs.get("rag_strategy", "system_message"),
            "memory_query": inputs.get("memory_query"),
            "memory_strategy": inputs.get("memory_strategy", memory_spec.get("type") or "planner_only"),
            "memory_top_k": inputs.get("memory_top_k", memory_policy.get("top_k") or 5),
            "context_window_messages": inputs.get("context_window_messages"),
            "context_window_chars": inputs.get("context_window_chars"),
            "verify": inputs.get("verify", policies.get("verify") if policies.get("verify") is not None else True),
            "failure_strategy": inputs.get("failure_strategy", policies.get("failure_strategy") or "respond"),
            "thread_id": inputs.get("thread_id"),
            "thread_title": inputs.get("thread_title"),
        }
        return AgentRunRequest.model_validate(payload)

    def _build_runner(self) -> AgentService:
        return AgentService(
            db=self.db,
            ctx=self.ctx,
            llm_port=self.llm_port,
            tool_port=self.tool_port,
            tool_resolver=self.tool_resolver,
            memory_service=self.memory_service,
            response_service=self.response_service,
            trace_writer=self.trace_writer,
        )

    def _resolve_thread_title(self, request: AgentRunRequest) -> Optional[str]:
        if request.thread_title:
            return request.thread_title
        for message in reversed(request.messages):
            if message.role == "user":
                return message.content[:120]
        return None

    def _response_input_payload(self, request: AgentRunRequest, *, agent_version_id: str) -> Dict[str, Any]:
        return {
            "messages": [message.model_dump(exclude_none=True) for message in request.messages],
            "model": request.model,
            "temperature": request.temperature,
            "thread_id": request.thread_id,
            "thread_title": request.thread_title,
            "agent_version_id": agent_version_id,
            "source": "agent.execute",
        }

    def _response_output_payload(self, result: Dict[str, Any]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "text": result.get("output") or "",
            "model": result.get("model"),
        }
        if result.get("finish_reason"):
            payload["finish_reason"] = result["finish_reason"]
        if result.get("iterations") is not None:
            payload["iterations"] = result["iterations"]
        return payload

    def _response_usage_payload(self, result: Dict[str, Any]) -> Dict[str, Any]:
        prompt_tokens = int(result.get("tokens_prompt") or 0)
        completion_tokens = int(result.get("tokens_completion") or 0)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "tool_calls": int(result.get("tool_calls") or 0),
            "llm_calls": int(result.get("llm_calls") or 0),
            "cost_total": float(result.get("cost_total") or 0.0),
        }

    def _task_output_payload(
        self,
        result: Dict[str, Any],
        *,
        response_id: Optional[str],
    ) -> Dict[str, Any]:
        return {
            "output": result.get("output") or "",
            "response_id": response_id,
            "model": result.get("model"),
            "finish_reason": result.get("finish_reason"),
            "iterations": result.get("iterations"),
            "tool_calls": int(result.get("tool_calls") or 0),
            "llm_calls": int(result.get("llm_calls") or 0),
            "cost_total": float(result.get("cost_total") or 0.0),
        }

    @rbac_guard(RESOURCE_AGENT, "create", resource_id_resolver=_resolve_agent_create_id)
    async def create_agent(self, data: AgentCreate) -> Agent:
        existing = self.agent_repo.get_by_name(data.name)
        if existing:
            raise ValidationError(f"Agent with name '{data.name}' already exists")

        return self.agent_repo.create(
            Agent(
                name=data.name,
                description=data.description,
                visibility=data.visibility,
                icon_url=data.icon_url,
                category=data.category,
                is_public=data.is_public,
                featured=data.featured,
                tags=data.tags,
            )
        )

    @rbac_guard(RESOURCE_AGENT, "update", resource_id_arg="agent_id")
    async def update_agent(self, agent_id: str, data: AgentUpdate) -> Agent:
        agent = self._get_agent(agent_id)
        if data.name and data.name != agent.name:
            existing = self.agent_repo.get_by_name(data.name)
            if existing and existing.id != agent.id:
                raise ValidationError(f"Agent with name '{data.name}' already exists")
            agent.name = data.name

        if data.description is not None:
            agent.description = data.description
        if data.status is not None:
            agent.status = data.status
        if data.visibility is not None:
            agent.visibility = data.visibility
        if data.icon_url is not None:
            agent.icon_url = data.icon_url
        if data.category is not None:
            agent.category = data.category
        if data.is_public is not None:
            agent.is_public = data.is_public
        if data.featured is not None:
            agent.featured = data.featured
        if data.tags is not None:
            agent.tags = data.tags
        return self.agent_repo.update(agent)

    @rbac_guard(RESOURCE_AGENT, "read", resource_id_arg="agent_id")
    async def get_agent(self, agent_id: str) -> Agent:
        return self._get_agent(agent_id)

    @workspace_guard("read")
    async def list_agents(self, limit: int = 20, offset: int = 0) -> List[Agent]:
        return self.agent_repo.list(limit=limit, offset=offset)

    @rbac_guard(RESOURCE_AGENT, "delete", resource_id_arg="agent_id")
    async def delete_agent(self, agent_id: str) -> None:
        agent = self._get_agent(agent_id)
        agent.status = "archived"
        agent.deleted_at = utc_now()
        self.agent_repo.update(agent)

    @rbac_guard(RESOURCE_AGENT, "update", resource_id_arg="agent_id")
    async def create_version(self, agent_id: str, data: AgentVersionCreate) -> AgentVersion:
        bindings = self._resolve_version_bindings(data)
        spec = self._build_spec(data, bindings)
        validate_runtime_spec("agent.v1", spec, raise_on_error=True)
        return self.versioning.create_draft(
            agent_id,
            spec_schema="agent.v1",
            spec_json=spec,
            metadata={"checksum": self._build_checksum(spec)},
        )

    @rbac_guard(RESOURCE_AGENT, "read", resource_id_arg="agent_id")
    async def list_versions(self, agent_id: str, limit: int = 20, offset: int = 0) -> List[AgentVersion]:
        return self.versioning.list_versions(agent_id, limit=limit, offset=offset)

    @rbac_guard(RESOURCE_AGENT, "read", resource_id_arg="agent_id")
    async def list_releases(self, agent_id: str, limit: int = 20, offset: int = 0) -> List[AgentPublish]:
        return self.versioning.list_releases(agent_id, limit=limit, offset=offset)

    @rbac_guard(RESOURCE_AGENT, "read", resource_id_arg="agent_id")
    async def list_bindings(self, agent_id: str, version_id: Optional[str] = None) -> List[AgentBinding]:
        agent = self._get_agent(agent_id)
        resolved_version_id = version_id or agent.current_version_id or agent.published_version_id
        if not resolved_version_id:
            return []
        version = self._get_version(resolved_version_id)
        if version.agent_id != agent.id:
            raise NotFoundError(f"Version not found: {resolved_version_id}")
        return self.binding_repo.list_for_version(version.id)

    @rbac_guard(RESOURCE_AGENT, "update", resource_id_arg="agent_id")
    async def publish_version(self, agent_id: str, version_id: str, *, notes: str | None = None) -> Agent:
        return self.versioning.publish(agent_id, version_id, notes=notes)

    @rbac_guard(RESOURCE_AGENT, "update", resource_id_arg="agent_id")
    async def rollback_version(self, agent_id: str, version_id: str, *, notes: str | None = None) -> Agent:
        return self.versioning.rollback(agent_id, version_id, notes=notes)

    @rbac_guard(RESOURCE_AGENT, "run", resource_id_arg="agent_id")
    async def execute_agent(self, agent_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        agent = self._get_agent(agent_id)
        version = self._resolve_execution_version(agent)
        request = self._request_from_version(version, inputs)
        linked_response = None

        thread = self.runtime_core.thread_repo.get_thread(request.thread_id) if request.thread_id else None
        if request.thread_id and not thread:
            raise NotFoundError(f"Thread not found: {request.thread_id}")
        if thread and thread.agent_id and thread.agent_id != agent.id:
            raise ValidationError(f"Thread {thread.id} does not belong to agent {agent.id}")
        if thread is None:
            thread = self.runtime_core.create_thread(
                agent_id=agent.id,
                title=self._resolve_thread_title(request),
                system_prompt=((version.spec_json or {}).get("system_prompt") if isinstance(version.spec_json, dict) else None),
                default_model_ref=request.model,
                default_temperature=request.temperature,
                max_history_messages=request.context_window_messages,
                max_history_chars=request.context_window_chars,
                metadata={"source": "agent.execute", "agent_version_id": version.id},
            )

        for message in request.messages:
            self.runtime_core.append_message(
                thread_id=thread.id,
                role=message.role,
                content=message.content,
                status="completed",
                metadata=message.metadata,
            )

        run = self.trace_writer.create_run(
            mode="agent",
            kind="agent",
            subject_kind="agent",
            subject_id=agent.id,
            subject_version_id=version.id,
            input_summary=request.messages[-1].content[:8192] if request.messages else None,
        )
        task = self.runtime_core.create_task(
            task_type="agent.execute",
            status=TaskStatus.PREPARING.value,
            agent_id=agent.id,
            thread_id=thread.id,
            run_id=run.id,
            input_payload={
                "agent_id": agent.id,
                "agent_version_id": version.id,
                "message_count": len(request.messages),
            },
        )
        self.runtime_core.transition_task(
            task_id=task.id,
            status=TaskStatus.RUNNING.value,
            progress={"phase": "agent_loop"},
        )

        if self.response_service:
            linked_response = self.response_service.create_linked_response(
                run_id=run.id,
                thread_id=thread.id,
                task_id=task.id,
                agent_id=agent.id,
                model=request.model,
                input_json=self._response_input_payload(request, agent_version_id=version.id),
                metadata_json={
                    "source": "agent.execute",
                    "agent_id": agent.id,
                    "agent_version_id": version.id,
                    "thread_id": thread.id,
                    "task_id": task.id,
                },
            )
            linked_response = self.response_service.mark_in_progress(linked_response)

        runner = self._build_runner()
        try:
            result = await runner.run(request, existing_run_id=run.id, response_id=linked_response.id if linked_response else None)
        except Exception as exc:
            if linked_response:
                linked_response = self.response_service.fail_response(
                    response=linked_response,
                    error_code="agent_execution_failed",
                    error_message=str(exc),
                    source="agent",
                )
            self.runtime_core.transition_task(
                task_id=task.id,
                status=TaskStatus.FAILED.value,
                error_code="agent_execution_failed",
                error_message=str(exc),
            )
            raise

        response_id = linked_response.id if linked_response else None
        self.runtime_core.append_message(
            thread_id=thread.id,
            role="assistant",
            content=result.get("output") or "",
            run_id=result.get("run_id"),
            task_id=task.id,
            response_id=response_id,
            status="completed",
            metadata={
                "agent_id": agent.id,
                "agent_version_id": version.id,
                "run_id": result.get("run_id"),
                "response_id": response_id,
            },
        )
        self.runtime_core.thread_repo.touch_thread(thread, latest_run_id=result.get("run_id"))
        self.runtime_core.transition_task(
            task_id=task.id,
            status=TaskStatus.SUCCEEDED.value,
            progress={"phase": "completed"},
            output_payload=self._task_output_payload(result, response_id=response_id),
        )
        if linked_response:
            linked_response = self.response_service.complete_response(
                response=linked_response,
                output_json=self._response_output_payload(result),
                usage_json=self._response_usage_payload(result),
                source="agent",
                output_event_payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "output": self._response_output_payload(result),
                    "usage": self._response_usage_payload(result),
                },
                completed_event_payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "status": "completed",
                    "usage": self._response_usage_payload(result),
                    "tool_calls": int(result.get("tool_calls") or 0),
                },
            )
        return {
            **result,
            "thread_id": thread.id,
            "task_id": task.id,
            "response_id": response_id,
        }
