"""Agent aggregate application service."""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from datetime import UTC
from typing import Any

from pydantic import BaseModel
from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.pagination import PageToken
from app.kernel.identity.guard import rbac_guard, workspace_guard
from app.kernel.identity.permissions import RESOURCE_AGENT
from app.kernel.ports.llm.interface import LLMPort
from app.kernel.ports.plugins.interface import PluginRuntimePort
from app.kernel.ports.tools.interface import ToolPort
from app.kernel.registry.deps import get_registry
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.tasks.service import TaskService
from app.kernel.runtime.tasks.status import TaskStatus
from app.kernel.runtime.threads.service import ThreadService
from app.kernel.runtime.tools.resolver import (
    BuiltinToolRegistrationPort,
    ToolResolver,
)
from app.kernel.specs.validator import validate_runtime_spec
from app.modules.agent.application.contracts import (
    AgentCapabilityCatalogPort,
    EmptyAgentCapabilityCatalog,
)
from app.modules.agent.application.schemas import (
    AgentCreate,
    AgentRunRequest,
    AgentRuntimeRequest,
    AgentUpdate,
    AgentVersionCreate,
    AgentWorkbenchCapability,
    AgentWorkbenchItemsResponse,
    AgentWorkbenchResponse,
    AgentWorkbenchRow,
    AgentWorkbenchSummary,
    AgentWorkbenchTabs,
)
from app.modules.agent.application.service import AgentService
from app.modules.agent.application.versioning_adapter import AgentVersioningAdapter
from app.modules.agent.domain.models import (
    Agent,
    AgentBinding,
    AgentPublish,
    AgentVersion,
)
from app.modules.agent.infra.repository import (
    AgentBindingRepository,
    AgentPublishRepository,
    AgentRepository,
    AgentVersionRepository,
)
from app.modules.agent.runtime.emitter import EventEmitter
from app.modules.evaluation.application.service import (
    RegressionEvaluationService,
    RegressionRunResult,
)
from app.modules.memory.application.service import MemoryService
from app.modules.versioning.application.service import VersionControlService


class AgentApplicationService:
    """Agent CRUD, publish, and execution service backed by Agent tables."""

    _INTERNAL_VERSION_OVERRIDE_KEY = "_agent_version_id"

    _BUILTIN_TOOL_REFS = {
        "tool:http:request",
        "tool:function:time_now",
        "tool:function:random_int",
        "tool:function:knowledge_query",
    }

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        *,
        llm_port: LLMPort,
        tool_port: ToolPort,
        memory_service: MemoryService | None = None,
        trace_writer: TraceWriter | None = None,
        response_service: ResponseService | None = None,
        approval_checkpoint_gateway: Any | None = None,
        regression_evaluator: RegressionEvaluationService | None = None,
        plugin_runtime_port: PluginRuntimePort | None = None,
        capability_catalog: AgentCapabilityCatalogPort | None = None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.llm_port = llm_port
        self.tool_port = tool_port
        self.memory_service = memory_service
        # Create ToolResolver if tool_port is a RegistryToolRouterPort
        self.tool_resolver = (
            ToolResolver(tool_port=tool_port)
            if isinstance(tool_port, BuiltinToolRegistrationPort)
            else None
        )
        self.trace_writer = trace_writer or TraceWriter(db, ctx)
        self.response_service = response_service or ResponseService(
            db=db,
            ctx=ctx,
            response_repo=ResponseRepository(db, ctx),
            event_repo=ResponseEventRepository(db, ctx),
            trace_writer=self.trace_writer,
        )
        self.regression_evaluator = regression_evaluator
        self.plugin_runtime_port = plugin_runtime_port
        self.capability_catalog = capability_catalog or EmptyAgentCapabilityCatalog()
        self.agent_repo = AgentRepository(db, ctx)
        self.version_repo = AgentVersionRepository(db, ctx)
        self.binding_repo = AgentBindingRepository(db, ctx)
        self.publish_repo = AgentPublishRepository(db, ctx)
        self.task_service = TaskService(db, ctx)
        self.thread_service = ThreadService(db, ctx)
        self.versioning = VersionControlService(
            AgentVersioningAdapter(
                agent_repo=self.agent_repo,
                version_repo=self.version_repo,
                publish_repo=self.publish_repo,
                sync_bindings=self._sync_bindings,
            ),
            ctx=ctx,
            approval_checkpoint_gateway=approval_checkpoint_gateway,
        )

    def _capability_item(
        self,
        *,
        ref: str,
        kind: str,
        name: str,
        source_kind: str,
        source_id: str | None = None,
        source_version: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "ref": ref,
            "kind": kind,
            "name": name,
            "source_kind": source_kind,
            "source_id": source_id,
            "source_version": source_version,
            "metadata_json": metadata_json or {},
        }

    def _tool_source_kind(self, ref: str, payload: dict[str, Any]) -> str:
        explicit = (payload.get("source_kind") or "").strip().lower()
        if explicit in {"builtin", "native", "plugin", "mcp"}:
            return explicit
        if payload.get("plugin"):
            return "plugin"
        if payload.get("mcp"):
            return "mcp"
        if payload.get("builtin") or ref in self._BUILTIN_TOOL_REFS:
            return "builtin"
        return "native"

    def _tool_capability_from_registry(self, key, payload: dict[str, Any]) -> dict[str, Any]:
        ref = key.name
        tool_spec = payload.get("tool_spec") or {}
        plugin = payload.get("plugin") or {}
        source_kind = self._tool_source_kind(ref, payload)
        source_id = payload.get("source_id")
        source_version = payload.get("source_version") or key.version
        if source_kind == "plugin":
            source_id = source_id or plugin.get("name")
            source_version = payload.get("source_version") or plugin.get("version") or key.version
        elif source_kind == "mcp":
            mcp_meta = payload.get("mcp") or {}
            source_id = source_id or mcp_meta.get("server_id") or mcp_meta.get("server_name") or mcp_meta.get("name")
            source_version = source_version or mcp_meta.get("server_version")
        elif source_kind == "builtin":
            source_id = source_id or ref
        else:
            source_id = source_id or ref
        metadata = {
            "registry_kind": key.kind,
            "registry_version": key.version,
            "tool_spec": tool_spec,
        }
        metadata.update({k: v for k, v in payload.items() if k not in {"tool_spec"}})
        return self._capability_item(
            ref=ref,
            kind="tool",
            name=str(tool_spec.get("name") or ref.split(":")[-1]),
            source_kind=source_kind,
            source_id=source_id,
            source_version=source_version,
            metadata_json=metadata,
        )

    def _model_capabilities(self) -> list[dict[str, Any]]:
        return self.capability_catalog.list_model_capabilities()

    def _knowledge_capabilities(self) -> list[dict[str, Any]]:
        return self.capability_catalog.list_knowledge_capabilities()

    def _workflow_capabilities(self) -> list[dict[str, Any]]:
        return self.capability_catalog.list_workflow_capabilities()

    def _plugin_artifact_capabilities(self) -> list[dict[str, Any]]:
        return self.capability_catalog.list_plugin_capabilities()

    def _tool_capabilities(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for key, payload in get_registry().list(
            kind="tool",
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
        ):
            payload_dict = payload if isinstance(payload, dict) else {}
            items.append(self._tool_capability_from_registry(key, payload_dict))
        return items

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

    def _normalize_ref_list(self, values: list[str] | None) -> list[str] | None:
        seen: set[str] = set()
        normalized: list[str] = []
        for value in values or []:
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized or None

    def _build_spec(self, data: AgentVersionCreate) -> dict[str, Any]:
        bindings = data.bindings
        memory_enabled = data.memory_strategy is not None or data.memory_top_k is not None
        memory_policy: dict[str, Any] = {}
        if data.memory_top_k is not None:
            memory_policy["top_k"] = data.memory_top_k
        limits: dict[str, Any] = {
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
            "temperature": data.temperature,
            "bindings": {
                "model_ref": bindings.model_ref,
                "knowledge_refs": self._normalize_ref_list(bindings.knowledge_refs),
                "tool_refs": self._normalize_ref_list(bindings.tool_refs),
                "workflow_refs": self._normalize_ref_list(bindings.workflow_refs),
                "skill_refs": self._normalize_ref_list(bindings.skill_refs),
            },
            "memory": {
                "enabled": memory_enabled or None,
                "type": data.memory_strategy,
                "policy": memory_policy or None,
            },
            "limits": limits,
            "policies": policies,
        }

    def _build_checksum(self, spec: dict[str, Any]) -> str:
        payload = json.dumps(spec, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _sync_bindings(
        self,
        agent: Agent,
        version: AgentVersion,
    ) -> None:
        spec = version.spec_json or {}
        binding_spec = spec.get("bindings") or {}
        model_ref = binding_spec.get("model_ref")
        bindings_to_create: list[AgentBinding] = []

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
            ("tool", binding_spec.get("tool_refs") or []),
            ("knowledge", binding_spec.get("knowledge_refs") or []),
            ("workflow", binding_spec.get("workflow_refs") or []),
            ("skill", binding_spec.get("skill_refs") or []),
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

    def _request_from_version(self, version: AgentVersion, inputs: dict[str, Any]) -> AgentRuntimeRequest:
        spec = version.spec_json or {}
        binding_spec = spec.get("bindings") or {}
        memory_spec = spec.get("memory") or {}
        memory_policy = (memory_spec.get("policy") or {}) if isinstance(memory_spec, dict) else {}
        limits = spec.get("limits") or {}
        policies = spec.get("policies") or {}
        public_request = AgentRunRequest.model_validate(inputs)
        raw_inputs = (
            inputs.model_dump(exclude_unset=True)
            if isinstance(inputs, BaseModel)
            else dict(inputs)
        )
        model_ref = binding_spec.get("model_ref")
        if not model_ref:
            raise ValidationError(f"Agent version {version.id} has no model binding")

        def first_defined(*values: Any, default: Any = None) -> Any:
            for value in values:
                if value is not None:
                    return value
            return default

        raw_memory_strategy = raw_inputs.get("memory_strategy")
        raw_memory_top_k = raw_inputs.get("memory_top_k")
        memory_enabled = bool(memory_spec.get("enabled")) if isinstance(memory_spec, dict) else False
        memory_strategy = None
        memory_top_k = None
        if raw_memory_strategy is not None or raw_memory_top_k is not None or raw_inputs.get("memory_query") is not None:
            memory_strategy = raw_memory_strategy or "planner_only"
            memory_top_k = raw_memory_top_k or 5
        elif memory_enabled:
            memory_strategy = memory_spec.get("type") or "planner_only"
            memory_top_k = memory_policy.get("top_k") or 5

        messages = [message.model_dump(exclude_none=True) for message in public_request.messages]
        system_prompt = spec.get("system_prompt")
        if system_prompt and not any(message.get("role") == "system" for message in messages):
            messages = [{"role": "system", "content": system_prompt}] + messages
        skill_context = self._resolve_skill_context(binding_spec.get("skill_refs") or [])
        if skill_context:
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] = f"{messages[0].get('content') or ''}\n\n{skill_context}".strip()
            else:
                messages = [{"role": "system", "content": skill_context}] + messages

        payload = {
            "messages": messages,
            "max_iterations": first_defined(raw_inputs.get("max_iterations"), limits.get("max_iterations"), default=8),
            "max_tool_calls": first_defined(raw_inputs.get("max_tool_calls"), limits.get("max_tool_calls"), default=8),
            "max_llm_calls": first_defined(raw_inputs.get("max_llm_calls"), limits.get("max_llm_calls"), default=16),
            "max_failures": first_defined(raw_inputs.get("max_failures"), limits.get("max_failures"), default=2),
            "max_runtime_seconds": raw_inputs.get(
                "max_runtime_seconds",
                int(limits["timeout_ms"] / 1000) if limits.get("timeout_ms") else None,
            ),
            "max_tokens_total": raw_inputs.get("max_tokens_total", limits.get("max_tokens")),
            "max_cost": raw_inputs.get("max_cost", limits.get("budget")),
            "cost_currency": raw_inputs.get("cost_currency", policies.get("cost_currency") or "USD"),
            "rag_top_k": raw_inputs.get("rag_top_k", 5),
            "rag_strategy": raw_inputs.get("rag_strategy", "system_message"),
            "memory_query": raw_inputs.get("memory_query"),
            "memory_strategy": memory_strategy,
            "memory_top_k": memory_top_k,
            "context_window_messages": raw_inputs.get("context_window_messages"),
            "context_window_chars": raw_inputs.get("context_window_chars"),
            "verify": raw_inputs.get("verify", policies.get("verify") if policies.get("verify") is not None else True),
            "failure_strategy": raw_inputs.get("failure_strategy", policies.get("failure_strategy") or "respond"),
            "thread_id": raw_inputs.get("thread_id"),
            "thread_title": raw_inputs.get("thread_title"),
            "model_ref": model_ref,
            "temperature": spec.get("temperature"),
            "knowledge_refs": binding_spec.get("knowledge_refs") or [],
            "tool_refs": binding_spec.get("tool_refs") or [],
            "workflow_refs": binding_spec.get("workflow_refs") or [],
            "skill_refs": binding_spec.get("skill_refs") or [],
            "system_prompt": system_prompt,
        }
        return AgentRuntimeRequest.model_validate(payload)

    def _resolve_skill_context(self, skill_refs: list[str]) -> str | None:
        if self.plugin_runtime_port:
            return self.plugin_runtime_port.resolve_skill_context(skill_refs=skill_refs, ctx=self.ctx)
        return self._resolve_skill_context_from_artifacts(skill_refs)

    def _resolve_skill_context_from_artifacts(self, skill_refs: list[str]) -> str | None:
        return self.capability_catalog.resolve_skill_context(skill_refs)

    def _build_runner(self) -> AgentService:
        async def execute_workflow_binding(workflow_ref: str, parameters: dict[str, Any]) -> dict[str, Any]:
            from app.modules.workflow.application.service import WorkflowService

            workflow_id = workflow_ref.split(":")[-1] if ":" in workflow_ref else workflow_ref
            workflow_service = WorkflowService(
                db=self.db,
                ctx=self.ctx,
                response_service=self.response_service,
            )
            return await workflow_service.execute_workflow(workflow_id, parameters or {})

        return AgentService(
            db=self.db,
            ctx=self.ctx,
            llm_port=self.llm_port,
            tool_port=self.tool_port,
            tool_resolver=self.tool_resolver,
            memory_service=self.memory_service,
            response_service=self.response_service,
            trace_writer=self.trace_writer,
            workflow_executor=execute_workflow_binding,
            capability_catalog=self.capability_catalog,
        )

    def _resolve_thread_title(self, request: AgentRuntimeRequest) -> str | None:
        if request.thread_title:
            return request.thread_title
        for message in reversed(request.messages):
            if message.role == "user":
                return message.content[:120]
        return None

    def _response_input_payload(self, request: AgentRuntimeRequest, *, agent_version_id: str) -> dict[str, Any]:
        return {
            "messages": [message.model_dump(exclude_none=True) for message in request.messages],
            "model": request.model_ref,
            "temperature": request.temperature,
            "thread_id": request.thread_id,
            "thread_title": request.thread_title,
            "agent_version_id": agent_version_id,
            "source": "agent.execute",
        }

    def _response_output_payload(self, result: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "text": result.get("output") or "",
            "model": result.get("model"),
        }
        if result.get("citations"):
            payload["citations"] = result["citations"]
        if result.get("finish_reason"):
            payload["finish_reason"] = result["finish_reason"]
        if result.get("iterations") is not None:
            payload["iterations"] = result["iterations"]
        if result.get("budget_exceeded"):
            payload["budget_exceeded"] = True
            payload["budget_reason"] = result.get("budget_reason")
        return payload

    def _response_usage_payload(self, result: dict[str, Any]) -> dict[str, Any]:
        prompt_tokens = int(result.get("tokens_prompt") or 0)
        completion_tokens = int(result.get("tokens_completion") or 0)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "tool_calls": int(result.get("tool_calls") or 0),
            "llm_calls": int(result.get("llm_calls") or 0),
            "cost_total": float(result.get("cost_total") or 0.0),
            "budget_exceeded": bool(result.get("budget_exceeded")),
            "budget_reason": result.get("budget_reason"),
        }

    def _task_output_payload(
        self,
        result: dict[str, Any],
        *,
        response_id: str | None,
    ) -> dict[str, Any]:
        return {
            "output": result.get("output") or "",
            "response_id": response_id,
            "model": result.get("model"),
            "finish_reason": result.get("finish_reason"),
            "iterations": result.get("iterations"),
            "tool_calls": int(result.get("tool_calls") or 0),
            "llm_calls": int(result.get("llm_calls") or 0),
            "cost_total": float(result.get("cost_total") or 0.0),
            "budget_exceeded": bool(result.get("budget_exceeded")),
            "budget_reason": result.get("budget_reason"),
        }

    def _assistant_message_metadata(
        self,
        agent: Agent,
        version: AgentVersion,
        result: dict[str, Any],
        *,
        response_id: str | None,
    ) -> dict[str, Any]:
        return {
            "agent_id": agent.id,
            "agent_version_id": version.id,
            "run_id": result.get("run_id"),
            "response_id": response_id,
            "model": result.get("model"),
            "finish_reason": result.get("finish_reason"),
            "tokens_prompt": result.get("tokens_prompt"),
            "tokens_completion": result.get("tokens_completion"),
            "tool_calls": result.get("tool_call_details") or [],
            "tool_calls_count": int(result.get("tool_calls") or 0),
            "llm_calls": int(result.get("llm_calls") or 0),
            "budget_exceeded": bool(result.get("budget_exceeded")),
            "budget_reason": result.get("budget_reason"),
            "cost_total": result.get("cost_total"),
            "citations": result.get("citations") or [],
        }

    def _append_failed_assistant_message(
        self,
        *,
        thread_id: str,
        task_id: str,
        run_id: str,
        agent: Agent,
        version: AgentVersion,
        response_id: str | None,
        error_code: str,
        error_message: str,
    ) -> None:
        metadata = {
            "agent_id": agent.id,
            "agent_version_id": version.id,
            "run_id": run_id,
            "response_id": response_id,
            "finish_reason": error_code,
            "error_code": error_code,
            "error_message": error_message,
            "tool_calls": [],
            "tool_calls_count": 0,
            "citations": [],
        }
        self.thread_service.append_message(
            thread_id=thread_id,
            role="assistant",
            content=f"Agent execution failed: {error_message}",
            run_id=run_id,
            task_id=task_id,
            response_id=response_id,
            status="failed",
            metadata=metadata,
            finish_reason=error_code,
            error_code=error_code,
            error_message=error_message,
        )
        self.thread_service.thread_repo.touch_thread(
            self.thread_service.thread_repo.get_thread(thread_id),
            latest_run_id=run_id,
        )

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
    async def list_agents(self, limit: int = 20, offset: int = 0) -> list[Agent]:
        return self.agent_repo.list(limit=limit, offset=offset)

    @workspace_guard("read")
    async def list_capabilities(
        self,
        *,
        kind: str | None = None,
        source_kind: str | None = None,
    ) -> list[dict[str, Any]]:
        items = [
            *self._model_capabilities(),
            *self._knowledge_capabilities(),
            *self._workflow_capabilities(),
            *self._tool_capabilities(),
            *self._plugin_artifact_capabilities(),
        ]
        deduped: dict[str, dict[str, Any]] = {}
        for item in items:
            deduped.setdefault(item["ref"], item)
        filtered = [
            item
            for item in deduped.values()
            if (kind is None or item["kind"] == kind)
            and (source_kind is None or item["source_kind"] == source_kind)
        ]
        return sorted(filtered, key=lambda entry: (entry["kind"], entry["source_kind"], entry["ref"]))

    @workspace_guard("read")
    async def get_workbench(self, limit: int = 20, offset: int = 0) -> AgentWorkbenchResponse:
        rows, runs_by_agent = self._build_workbench_rows()
        all_today_runs = [
            run
            for agent_runs in runs_by_agent.values()
            for run in agent_runs
            if self._is_today(run.started_at)
        ]
        summary = self._build_workbench_summary(rows, all_today_runs)
        tabs = AgentWorkbenchTabs(
            all=len(rows),
            high_calls=sum(1 for row in rows if row.today_calls >= 100),
            low_success=sum(1 for row in rows if row.success_rate is not None and row.success_rate < 98),
            long_latency=sum(1 for row in rows if row.avg_latency_ms is not None and row.avg_latency_ms >= 300),
            unconfigured=sum(1 for row in rows if row.status == "unconfigured"),
        )

        visible_rows = rows[offset: offset + limit]
        has_next = offset + len(visible_rows) < len(rows)
        next_page_token = PageToken(offset=offset + len(visible_rows), limit=limit).to_string() if has_next else None
        return AgentWorkbenchResponse(
            summary=summary,
            tabs=tabs,
            items=visible_rows,
            next_page_token=next_page_token,
            page_size=len(visible_rows),
        )

    @workspace_guard("read")
    async def get_workbench_items(
        self,
        limit: int = 20,
        offset: int = 0,
        tab: str | None = None,
        keyword: str | None = None,
    ) -> AgentWorkbenchItemsResponse:
        rows, _ = self._build_workbench_rows()
        filtered_rows = self._filter_workbench_rows(rows, tab=tab, keyword=keyword)
        visible_rows = filtered_rows[offset: offset + limit]
        has_next = offset + len(visible_rows) < len(filtered_rows)
        next_page_token = PageToken(offset=offset + len(visible_rows), limit=limit).to_string() if has_next else None
        return AgentWorkbenchItemsResponse(
            items=visible_rows,
            next_page_token=next_page_token,
            page_size=len(visible_rows),
        )

    def _build_workbench_rows(self) -> tuple[list[AgentWorkbenchRow], dict[str, list[Run]]]:
        agents = self._list_workbench_agents()
        agent_ids = [agent.id for agent in agents]
        runs_by_agent = self._workbench_runs_by_agent(agent_ids)
        bindings_by_version = self._workbench_bindings_by_version(
            [agent.published_version_id for agent in agents if agent.published_version_id]
        )
        rows = [
            self._build_workbench_row(
                agent,
                runs_by_agent.get(agent.id, []),
                bindings_by_version.get(agent.published_version_id or "", []),
            )
            for agent in agents
        ]
        return rows, runs_by_agent

    def _filter_workbench_rows(
        self,
        rows: list[AgentWorkbenchRow],
        *,
        tab: str | None,
        keyword: str | None,
    ) -> list[AgentWorkbenchRow]:
        normalized_tab = (tab or "all").strip().lower()
        normalized_keyword = (keyword or "").strip().lower()

        def tab_matches(row: AgentWorkbenchRow) -> bool:
            if normalized_tab in {"", "all"}:
                return True
            if normalized_tab == "high":
                return row.today_calls >= 100
            if normalized_tab == "low-success":
                return row.success_rate is not None and row.success_rate < 98
            if normalized_tab == "long-latency":
                return row.avg_latency_ms is not None and row.avg_latency_ms >= 300
            return row.status == normalized_tab

        def keyword_matches(row: AgentWorkbenchRow) -> bool:
            if not normalized_keyword:
                return True
            capability_text = " ".join(
                " ".join(filter(None, [capability.type, capability.target_key, capability.target_id, capability.label]))
                for capability in row.capabilities
            )
            haystack = " ".join(
                filter(
                    None,
                    [
                        row.name,
                        row.description,
                        row.owner,
                        row.status,
                        capability_text,
                    ],
                )
            ).lower()
            return normalized_keyword in haystack

        return [row for row in rows if tab_matches(row) and keyword_matches(row)]

    def _list_workbench_agents(self) -> list[Agent]:
        query = (
            select(Agent)
            .where(
                and_(
                    Agent.tenant_id == self.ctx.tenant_id,
                    Agent.workspace_id == self.ctx.workspace_id,
                    Agent.deleted_at.is_(None),
                )
            )
            .order_by(desc(Agent.updated_at))
        )
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, Agent) else item[0] for item in results]

    def _workbench_runs_by_agent(self, agent_ids: list[str]) -> dict[str, list[Run]]:
        if not agent_ids:
            return {}
        query = (
            select(Run)
            .where(
                and_(
                    Run.tenant_id == self.ctx.tenant_id,
                    Run.workspace_id == self.ctx.workspace_id,
                    Run.subject_kind == "agent",
                    Run.subject_id.in_(agent_ids),
                )
            )
            .order_by(desc(Run.started_at))
        )
        results = list(self.db.exec(query).all())
        grouped: dict[str, list[Run]] = defaultdict(list)
        for item in results:
            run = item if isinstance(item, Run) else item[0]
            if run.subject_id:
                grouped[run.subject_id].append(run)
        return grouped

    def _workbench_bindings_by_version(self, version_ids: list[str]) -> dict[str, list[AgentBinding]]:
        if not version_ids:
            return {}
        query = (
            select(AgentBinding)
            .where(
                and_(
                    AgentBinding.tenant_id == self.ctx.tenant_id,
                    AgentBinding.workspace_id == self.ctx.workspace_id,
                    AgentBinding.agent_version_id.in_(version_ids),
                )
            )
            .order_by(AgentBinding.sort_order.asc(), AgentBinding.created_at.asc())
        )
        results = list(self.db.exec(query).all())
        grouped: dict[str, list[AgentBinding]] = defaultdict(list)
        for item in results:
            binding = item if isinstance(item, AgentBinding) else item[0]
            grouped[binding.agent_version_id].append(binding)
        return grouped

    def _build_workbench_row(
        self,
        agent: Agent,
        runs: list[Run],
        bindings: list[AgentBinding],
    ) -> AgentWorkbenchRow:
        today_runs = [run for run in runs if self._is_today(run.started_at)]
        metric_runs = today_runs if today_runs else runs
        avg_latency_ms = self._average_latency(metric_runs)
        success_rate = self._success_rate(metric_runs)
        exception_count = sum(1 for run in metric_runs if self._run_failed(run))
        status = self._resolve_workbench_status(agent, exception_count, success_rate)
        binding_order = {"model": 0, "knowledge": 1, "tool": 2, "workflow": 3, "skill": 4, "plugin": 5}
        sorted_bindings = sorted(
            bindings,
            key=lambda binding: (binding_order.get(binding.binding_type, 99), binding.sort_order, binding.created_at),
        )
        return AgentWorkbenchRow(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            status=status,
            capabilities=[
                AgentWorkbenchCapability(
                    type=binding.binding_type,
                    target_id=binding.target_id,
                    target_key=binding.target_key,
                    label=binding.target_key or binding.target_id or binding.binding_type,
                )
                for binding in sorted_bindings
            ],
            today_calls=len(today_runs),
            avg_latency_ms=avg_latency_ms,
            success_rate=success_rate,
            recent_exception_count=exception_count,
            owner=agent.updated_by or agent.created_by,
            last_run_at=runs[0].started_at if runs else None,
            action_enabled=agent.status == "active" and bool(agent.published_version_id),
            updated_at=agent.updated_at,
        )

    def _build_workbench_summary(self, rows: list[AgentWorkbenchRow], today_runs: list[Run]) -> AgentWorkbenchSummary:
        return AgentWorkbenchSummary(
            total_agents=len(rows),
            configured_agents=sum(1 for row in rows if row.status != "unconfigured"),
            running_agents=sum(1 for row in rows if row.action_enabled),
            today_calls=len(today_runs),
            avg_latency_ms=self._average_latency(today_runs),
            success_rate=self._success_rate(today_runs),
            pending_exceptions=sum(1 for run in today_runs if self._run_failed(run)),
            updated_at=utc_now(),
        )

    def _resolve_workbench_status(
        self,
        agent: Agent,
        exception_count: int,
        success_rate: float | None,
    ) -> str:
        if not agent.published_version_id:
            return "configuring" if agent.current_version_id else "unconfigured"
        if agent.status != "active":
            return "configuring"
        if exception_count > 0 or (success_rate is not None and success_rate < 95):
            return "abnormal"
        return "running"

    def _is_today(self, value) -> bool:
        if value is None:
            return False
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        return value >= start

    def _average_latency(self, runs: list[Run]) -> int | None:
        durations = [run.duration_ms for run in runs if run.duration_ms is not None]
        if not durations:
            return None
        return int(round(sum(durations) / len(durations)))

    def _success_rate(self, runs: list[Run]) -> float | None:
        if not runs:
            return None
        successes = sum(1 for run in runs if run.status in {"succeeded", "completed"})
        return round((successes / len(runs)) * 100, 1)

    def _run_failed(self, run: Run) -> bool:
        return run.status == "failed" or bool(run.error_message)

    @rbac_guard(RESOURCE_AGENT, "delete", resource_id_arg="agent_id")
    async def delete_agent(self, agent_id: str) -> None:
        agent = self._get_agent(agent_id)
        agent.status = "archived"
        agent.deleted_at = utc_now()
        self.agent_repo.update(agent)

    @rbac_guard(RESOURCE_AGENT, "update", resource_id_arg="agent_id")
    async def create_version(self, agent_id: str, data: AgentVersionCreate) -> AgentVersion:
        spec = self._build_spec(data)
        validate_runtime_spec("agent.v1", spec, raise_on_error=True)
        return self.versioning.create_draft(
            agent_id,
            spec_schema="agent.v1",
            spec_json=spec,
            metadata={"checksum": self._build_checksum(spec)},
        )

    @rbac_guard(RESOURCE_AGENT, "read", resource_id_arg="agent_id")
    async def list_versions(self, agent_id: str, limit: int = 20, offset: int = 0) -> list[AgentVersion]:
        return self.versioning.list_versions(agent_id, limit=limit, offset=offset)

    @rbac_guard(RESOURCE_AGENT, "read", resource_id_arg="agent_id")
    async def list_releases(self, agent_id: str, limit: int = 20, offset: int = 0) -> list[AgentPublish]:
        return self.versioning.list_releases(agent_id, limit=limit, offset=offset)

    @rbac_guard(RESOURCE_AGENT, "read", resource_id_arg="agent_id")
    async def list_bindings(self, agent_id: str, version_id: str | None = None) -> list[AgentBinding]:
        agent = self._get_agent(agent_id)
        resolved_version_id = version_id or agent.current_version_id or agent.published_version_id
        if not resolved_version_id:
            return []
        version = self._get_version(resolved_version_id)
        if version.agent_id != agent.id:
            raise NotFoundError(f"Version not found: {resolved_version_id}")
        return self.binding_repo.list_for_version(version.id)

    async def _evaluate_regressions_before_publish(self, agent_id: str, version_id: str) -> None:
        if self.regression_evaluator is None:
            return
        cases = self.regression_evaluator.list_cases(subject_kind="agent", subject_id=agent_id)
        if not cases:
            return
        result = await self.regression_evaluator.evaluate_subject_version(
            subject_kind="agent",
            subject_id=agent_id,
            subject_version_id=version_id,
            runner=lambda case: self._replay_regression_case(agent_id, version_id, case),
        )
        if result.passed:
            return
        raise ValidationError(
            "Agent regression evaluation failed",
            details={
                "status": "regression_failed",
                "report_id": result.report_id,
                "summary": result.summary,
                "cases": result.cases,
            },
        )

    async def _replay_regression_case(
        self,
        agent_id: str,
        version_id: str,
        case: Any,
    ) -> RegressionRunResult:
        started = time.perf_counter()
        result = await self.execute_agent(
            agent_id,
            {
                **self._agent_inputs_from_regression_case(case),
                self._INTERNAL_VERSION_OVERRIDE_KEY: version_id,
            },
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        return RegressionRunResult(
            output=str(result.get("output") or ""),
            latency_ms=latency_ms,
            cost={
                "amount": float(result.get("cost_total") or 0.0),
                "currency": result.get("cost_currency") or "USD",
            },
            run_id=result.get("run_id"),
        )

    def _agent_inputs_from_regression_case(self, case: Any) -> dict[str, Any]:
        snapshot = dict(case.input_snapshot_json or {})
        if snapshot.get("messages"):
            return snapshot
        if snapshot.get("input_summary"):
            return {"messages": [{"role": "user", "content": str(snapshot["input_summary"])}]}
        if snapshot.get("input") is not None:
            content = snapshot["input"]
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
            return {"messages": [{"role": "user", "content": content}]}
        return {"messages": [{"role": "user", "content": json.dumps(snapshot, ensure_ascii=False)}]}

    @rbac_guard(RESOURCE_AGENT, "update", resource_id_arg="agent_id")
    async def publish_version(self, agent_id: str, version_id: str, *, notes: str | None = None) -> Agent:
        await self._evaluate_regressions_before_publish(agent_id, version_id)
        return self.versioning.publish(agent_id, version_id, notes=notes)

    @rbac_guard(RESOURCE_AGENT, "update", resource_id_arg="agent_id")
    async def rollback_version(self, agent_id: str, version_id: str, *, notes: str | None = None) -> Agent:
        return self.versioning.rollback(agent_id, version_id, notes=notes)

    @rbac_guard(RESOURCE_AGENT, "run", resource_id_arg="agent_id")
    async def execute_agent(self, agent_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        agent = self._get_agent(agent_id)
        inputs = dict(inputs)
        version_override_id = inputs.pop(self._INTERNAL_VERSION_OVERRIDE_KEY, None)
        if version_override_id:
            version = self._get_version(version_override_id)
            if version.agent_id != agent.id:
                raise NotFoundError(f"Version not found: {version_override_id}")
        else:
            version = self._resolve_execution_version(agent)
        request = self._request_from_version(version, inputs)
        linked_response = None

        thread = self.thread_service.thread_repo.get_thread(request.thread_id) if request.thread_id else None
        if request.thread_id and not thread:
            raise NotFoundError(f"Thread not found: {request.thread_id}")
        if thread and thread.agent_id and thread.agent_id != agent.id:
            raise ValidationError(f"Thread {thread.id} does not belong to agent {agent.id}")
        if thread is None:
            thread = self.thread_service.create_thread(
                agent_id=agent.id,
                title=self._resolve_thread_title(request),
                system_prompt=((version.spec_json or {}).get("system_prompt") if isinstance(version.spec_json, dict) else None),
                default_model_ref=request.model_ref,
                default_temperature=request.temperature,
                max_history_messages=request.context_window_messages,
                max_history_chars=request.context_window_chars,
                metadata={"source": "agent.execute", "agent_version_id": version.id},
            )

        for message in request.messages:
            self.thread_service.append_message(
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
        task = self.task_service.create_task(
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
        self.task_service.transition_task(
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
                model=request.model_ref,
                input_json=self._response_input_payload(request, agent_version_id=version.id),
                metadata_json={
                    "source": "agent.execute",
                    "agent_id": agent.id,
                    "agent_version_id": version.id,
                    "thread_id": thread.id,
                    "task_id": task.id,
                },
            )
            linked_response = self.response_service.mark_running(linked_response)

        runner = self._build_runner()
        try:
            result = await runner.run(request, existing_run_id=run.id, response_id=linked_response.id if linked_response else None)
        except Exception as exc:
            error_message = str(exc)
            if linked_response:
                linked_response = self.response_service.fail_response(
                    response=linked_response,
                    error_code="agent_execution_failed",
                    error_message=error_message,
                    source="agent",
                )
            self._append_failed_assistant_message(
                thread_id=thread.id,
                task_id=task.id,
                run_id=run.id,
                agent=agent,
                version=version,
                response_id=linked_response.id if linked_response else None,
                error_code="agent_execution_failed",
                error_message=error_message,
            )
            self.task_service.transition_task(
                task_id=task.id,
                status=TaskStatus.FAILED.value,
                error_code="agent_execution_failed",
                error_message=error_message,
            )
            raise

        response_id = linked_response.id if linked_response else None
        self.thread_service.append_message(
            thread_id=thread.id,
            role="assistant",
            content=result.get("output") or "",
            run_id=result.get("run_id"),
            task_id=task.id,
            response_id=response_id,
            status="completed",
            metadata=self._assistant_message_metadata(agent, version, result, response_id=response_id),
            citations_json=result.get("citations") or [],
            tokens_prompt=result.get("tokens_prompt"),
            tokens_completion=result.get("tokens_completion"),
            finish_reason=result.get("finish_reason"),
            tool_calls_json=result.get("tool_call_details") or [],
        )
        self.thread_service.thread_repo.touch_thread(thread, latest_run_id=result.get("run_id"))
        self.task_service.transition_task(
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
                    "status": "succeeded",
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

    @rbac_guard(RESOURCE_AGENT, "run", resource_id_arg="agent_id")
    async def execute_agent_streaming(
        self,
        agent_id: str,
        inputs: dict[str, Any],
        event_emitter: EventEmitter,
    ) -> dict[str, Any]:
        """Execute agent with event streaming via the provided emitter.

        Same lifecycle as execute_agent but passes event_emitter to the runner
        so callers can observe events in real time (e.g. SSE).
        """
        agent = self._get_agent(agent_id)
        version = self._resolve_execution_version(agent)
        request = self._request_from_version(version, inputs)
        linked_response = None

        thread = self.thread_service.thread_repo.get_thread(request.thread_id) if request.thread_id else None
        if request.thread_id and not thread:
            raise NotFoundError(f"Thread not found: {request.thread_id}")
        if thread and thread.agent_id and thread.agent_id != agent.id:
            raise ValidationError(f"Thread {thread.id} does not belong to agent {agent.id}")
        if thread is None:
            thread = self.thread_service.create_thread(
                agent_id=agent.id,
                title=self._resolve_thread_title(request),
                system_prompt=((version.spec_json or {}).get("system_prompt") if isinstance(version.spec_json, dict) else None),
                default_model_ref=request.model_ref,
                default_temperature=request.temperature,
                max_history_messages=request.context_window_messages,
                max_history_chars=request.context_window_chars,
                metadata={"source": "agent.stream", "agent_version_id": version.id},
            )

        for message in request.messages:
            self.thread_service.append_message(
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
        task = self.task_service.create_task(
            task_type="agent.stream",
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
        self.task_service.transition_task(
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
                model=request.model_ref,
                input_json=self._response_input_payload(request, agent_version_id=version.id),
                metadata_json={
                    "source": "agent.stream",
                    "agent_id": agent.id,
                    "agent_version_id": version.id,
                    "thread_id": thread.id,
                    "task_id": task.id,
                },
            )
            linked_response = self.response_service.mark_running(linked_response)

        runner = self._build_runner()
        try:
            result = await runner.run(
                request,
                existing_run_id=run.id,
                response_id=linked_response.id if linked_response else None,
                event_emitter=event_emitter,
            )
        except Exception as exc:
            error_message = str(exc)
            if linked_response:
                linked_response = self.response_service.fail_response(
                    response=linked_response,
                    error_code="agent_execution_failed",
                    error_message=error_message,
                    source="agent",
                )
            self._append_failed_assistant_message(
                thread_id=thread.id,
                task_id=task.id,
                run_id=run.id,
                agent=agent,
                version=version,
                response_id=linked_response.id if linked_response else None,
                error_code="agent_execution_failed",
                error_message=error_message,
            )
            await event_emitter(
                "agent.run.failed",
                {
                    "run_id": run.id,
                    "thread_id": thread.id,
                    "task_id": task.id,
                    "response_id": linked_response.id if linked_response else None,
                    "error_code": "agent_execution_failed",
                    "error_message": error_message,
                },
            )
            self.task_service.transition_task(
                task_id=task.id,
                status=TaskStatus.FAILED.value,
                error_code="agent_execution_failed",
                error_message=error_message,
            )
            raise

        response_id = linked_response.id if linked_response else None
        self.thread_service.append_message(
            thread_id=thread.id,
            role="assistant",
            content=result.get("output") or "",
            run_id=result.get("run_id"),
            task_id=task.id,
            response_id=response_id,
            status="completed",
            metadata=self._assistant_message_metadata(agent, version, result, response_id=response_id),
            citations_json=result.get("citations") or [],
            tokens_prompt=result.get("tokens_prompt"),
            tokens_completion=result.get("tokens_completion"),
            finish_reason=result.get("finish_reason"),
            tool_calls_json=result.get("tool_call_details") or [],
        )
        self.thread_service.thread_repo.touch_thread(thread, latest_run_id=result.get("run_id"))
        self.task_service.transition_task(
            task_id=task.id,
            status=TaskStatus.SUCCEEDED.value,
            progress={"phase": "completed"},
            output_payload=self._task_output_payload(result, response_id=response_id),
        )
        if linked_response:
            self.response_service.complete_response(
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
                    "status": "succeeded",
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
