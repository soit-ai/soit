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
from app.modules.agent.application.schemas import AgentCreate, AgentRunRequest, AgentUpdate, AgentVersionCreate
from app.modules.agent.application.service import AgentService
from app.modules.agent.domain.models import Agent, AgentBinding, AgentPublish, AgentVersion
from app.modules.agent.infra.repository import (
    AgentBindingRepository,
    AgentPublishRepository,
    AgentRepository,
    AgentVersionRepository,
)
from app.modules.memory.application.service import MemoryService


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
        version_id = agent.published_version_id or agent.current_version_id
        if not version_id:
            raise ValidationError(f"Agent has no version to execute: {agent.id}")
        version = self._get_version(version_id)
        if version.agent_id != agent.id:
            raise ValidationError(f"Version {version.id} does not belong to agent {agent.id}")
        return version

    def _build_spec(self, data: AgentVersionCreate) -> Dict[str, Any]:
        memory_enabled = data.memory_strategy is not None or data.memory_top_k is not None
        memory_policy: Dict[str, Any] = {}
        if data.memory_top_k is not None:
            memory_policy["top_k"] = data.memory_top_k
        knowledge_refs = [item for item in (data.knowledge_refs or []) if item]
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
                "ref_key": data.model_ref,
                "params": {"temperature": data.temperature} if data.temperature is not None else {},
            },
            "tools": {
                "allowlist": data.tool_refs,
                "configs": None,
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

    def _sync_bindings(self, agent: Agent, version: AgentVersion) -> None:
        spec = version.spec_json or {}
        model_ref = ((spec.get("model") or {}).get("ref_key") if isinstance(spec.get("model"), dict) else None)
        if model_ref:
            self.binding_repo.create(
                AgentBinding(
                    agent_id=agent.id,
                    agent_version_id=version.id,
                    binding_type="model",
                    target_key=model_ref,
                    config_json={},
                )
            )

        tool_refs = (spec.get("tools") or {}).get("allowlist") or []
        for sort_order, tool_ref in enumerate(tool_refs):
            if not tool_ref:
                continue
            self.binding_repo.create(
                AgentBinding(
                    agent_id=agent.id,
                    agent_version_id=version.id,
                    binding_type="tool",
                    target_key=tool_ref,
                    config_json={},
                    sort_order=sort_order,
                )
            )

        knowledge_refs = (spec.get("rag") or {}).get("knowledges") or []
        for sort_order, knowledge_ref in enumerate(knowledge_refs):
            if not knowledge_ref:
                continue
            self.binding_repo.create(
                AgentBinding(
                    agent_id=agent.id,
                    agent_version_id=version.id,
                    binding_type="knowledge",
                    target_key=knowledge_ref,
                    config_json={},
                    sort_order=sort_order,
                )
            )

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
        agent = self._get_agent(agent_id)
        spec = self._build_spec(data)
        validate_runtime_spec("agent.v1", spec, raise_on_error=True)

        version = self.version_repo.create(
            AgentVersion(
                agent_id=agent_id,
                version=self.agent_repo.next_version_number(agent_id),
                status="draft",
                spec_schema="agent.v1",
                spec_json=spec,
                checksum=self._build_checksum(spec),
                created_from_version_id=agent.current_version_id,
            )
        )
        self._sync_bindings(agent, version)

        agent.current_version_id = version.id
        if not agent.default_model_ref:
            agent.default_model_ref = ((spec.get("model") or {}).get("ref_key") if isinstance(spec.get("model"), dict) else None)
        self.agent_repo.update(agent)
        return version

    @rbac_guard(RESOURCE_AGENT, "read", resource_id_arg="agent_id")
    async def list_versions(self, agent_id: str, limit: int = 20, offset: int = 0) -> List[AgentVersion]:
        self._get_agent(agent_id)
        return self.version_repo.list_by_agent(agent_id, limit=limit, offset=offset)

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
    async def publish_version(self, agent_id: str, version_id: str) -> Agent:
        agent = self._get_agent(agent_id)
        version = self._get_version(version_id)
        if version.agent_id != agent.id:
            raise NotFoundError(f"Version not found: {version_id}")

        version.status = "published"
        self.version_repo.update(version)
        self.publish_repo.create(
            AgentPublish(
                agent_id=agent.id,
                agent_version_id=version.id,
            )
        )
        agent.current_version_id = version.id
        agent.published_version_id = version.id
        if agent.published_at is None:
            agent.published_at = utc_now()
        self.agent_repo.update(agent)
        return agent

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

        task = self.runtime_core.create_task(
            task_type="agent.execute",
            status=TaskStatus.PREPARING.value,
            agent_id=agent.id,
            thread_id=thread.id,
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

        run = self.trace_writer.create_run(
            mode="agent",
            kind="agent",
            subject_kind="agent",
            subject_id=agent.id,
            subject_version_id=version.id,
            input_summary=request.messages[-1].content[:8192] if request.messages else None,
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
            linked_response.status = "in_progress"
            linked_response = self.response_service.save_response(linked_response)

        runner = self._build_runner()
        try:
            result = await runner.run(request, existing_run_id=run.id, response_id=linked_response.id if linked_response else None)
        except Exception as exc:
            if linked_response:
                linked_response.status = "failed"
                linked_response.error_code = "agent_execution_failed"
                linked_response.error_message = str(exc)
                linked_response = self.response_service.save_response(linked_response)
                self.response_service.append_event(
                    response=linked_response,
                    event_type="response.failed",
                    payload={
                        "response_id": linked_response.id,
                        "run_id": linked_response.run_id,
                        "status": linked_response.status,
                        "error": {"code": linked_response.error_code, "message": linked_response.error_message},
                    },
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
            model_ref=result.get("model"),
            tokens_prompt=int(result.get("tokens_prompt") or 0),
            tokens_completion=int(result.get("tokens_completion") or 0),
            finish_reason=result.get("finish_reason"),
            metadata={
                "agent_id": agent.id,
                "agent_version_id": version.id,
                "run_id": result.get("run_id"),
                "model": result.get("model"),
                "response_id": response_id,
            },
        )
        self.runtime_core.thread_repo.touch_thread(thread, latest_run_id=result.get("run_id"))
        self.runtime_core.transition_task(
            task_id=task.id,
            status=TaskStatus.SUCCEEDED.value,
            progress={"phase": "completed"},
            output_payload=result,
        )
        if linked_response:
            linked_response.output_json = self._response_output_payload(result)
            linked_response.usage_json = self._response_usage_payload(result)
            linked_response.status = "completed"
            linked_response.completed_at = utc_now()
            linked_response.error_code = None
            linked_response.error_message = None
            linked_response = self.response_service.save_response(linked_response)
            self.response_service.append_event(
                response=linked_response,
                event_type="response.output_text.completed",
                payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "output": linked_response.output_json,
                    "usage": linked_response.usage_json,
                },
                source="agent",
            )
            self.response_service.append_event(
                response=linked_response,
                event_type="response.completed",
                payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "status": linked_response.status,
                    "usage": linked_response.usage_json,
                    "tool_calls": int(result.get("tool_calls") or 0),
                },
                source="agent",
            )
        return {
            **result,
            "thread_id": thread.id,
            "task_id": task.id,
            "response_id": response_id,
        }
