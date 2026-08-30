"""Agent aggregate application service."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import UTC
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import (
    KernelError,
    NotFoundError,
    ValidationError,
    public_error_message,
)
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.pagination import PageToken
from app.kernel.identity.guard import rbac_guard, workspace_guard
from app.kernel.identity.permissions import RESOURCE_AGENT
from app.kernel.ports.llm.interface import LLMPort
from app.kernel.ports.plugins.interface import PluginRuntimePort
from app.kernel.ports.tools.interface import ToolPort
from app.kernel.ports.tools.sandbox import SandboxToolPort
from app.kernel.registry.deps import get_registry
from app.kernel.runtime.attachments.service import AttachmentService
from app.kernel.runtime.db.models.responses import (
    Response,
    ResponseInteraction,
    generate_response_interaction_id,
)
from app.kernel.runtime.db.models.runs import Run, RunArtifact
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.db.models.threads import generate_thread_message_id
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.status import TaskStatus
from app.kernel.runtime.tasks.service import TaskService
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
    ChatMessageInput,
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
from app.modules.identity.application.display import resolve_user_display_names
from app.modules.memory.application.service import MemoryService
from app.modules.versioning.application.service import VersionControlService

if TYPE_CHECKING:
    from app.modules.workflow.application.contracts import WorkflowKnowledgeQueryPort

logger = logging.getLogger(__name__)
_PUBLIC_AGENT_EXECUTION_ERROR = "Agent execution failed"


class AgentApplicationService:
    """Agent CRUD, publish, and execution service backed by Agent tables."""

    _INTERNAL_VERSION_OVERRIDE_KEY = "_agent_version_id"

    _INTERNAL_SANDBOX_KEY = "_agent_sandbox"
    """Marks an execution as a rehearsal.

    A rehearsal exercises the whole decision path -- the model call, the
    bindings, the policy checks -- but stops tool calls at the boundary. Without
    it, testing a release creates tickets, pages people and charges third
    parties for work nobody asked for.
    """

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
        attachment_service: AttachmentService | None = None,
        approval_checkpoint_gateway: Any | None = None,
        regression_evaluator: RegressionEvaluationService | None = None,
        plugin_runtime_port: PluginRuntimePort | None = None,
        capability_catalog: AgentCapabilityCatalogPort | None = None,
        workflow_knowledge_query_port: WorkflowKnowledgeQueryPort | None = None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.llm_port = llm_port
        self.tool_port = tool_port
        self.memory_service = memory_service
        self.workflow_knowledge_query_port = workflow_knowledge_query_port
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
        self.attachment_service = attachment_service
        self.approval_checkpoint_gateway = approval_checkpoint_gateway
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

    def published_model_ref(self, agent_id: str) -> str | None:
        """Return the model the agent's published version binds, if any.

        Callers that name an agent but no model -- `/responses` is the one that
        matters -- would otherwise fall back to a hardcoded default that no
        workspace is obliged to have a route for.
        """
        agent = self.agent_repo.get_by_id(agent_id)
        if agent is None or not agent.published_version_id:
            return None
        version = self.version_repo.get_by_id(agent.published_version_id)
        if version is None or version.agent_id != agent.id:
            return None
        bindings = (version.spec_json or {}).get("bindings") or {}
        model_ref = bindings.get("model_ref")
        return str(model_ref) if model_ref else None

    def _normalize_ref_list(self, values: list[str] | None) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for value in values or []:
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized

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
            "rag_top_k": data.rag_top_k,
            "context_window_messages": data.context_window_messages,
            "context_window_chars": data.context_window_chars,
        }
        policies = {
            "verify": data.verify,
            "failure_strategy": data.failure_strategy,
            "cost_currency": data.cost_currency,
            "rag_strategy": data.rag_strategy,
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
        model_ref = binding_spec.get("model_ref")
        if not model_ref:
            raise ValidationError(f"Agent version {version.id} has no model binding")

        def first_defined(*values: Any, default: Any = None) -> Any:
            for value in values:
                if value is not None:
                    return value
            return default

        memory_enabled = bool(memory_spec.get("enabled")) if isinstance(memory_spec, dict) else False
        memory_strategy = (memory_spec.get("type") or "planner_only") if memory_enabled else None
        memory_top_k = (memory_policy.get("top_k") or 5) if memory_enabled else None

        messages = [{"role": "user", "content": public_request.input}]
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
            "max_iterations": first_defined(limits.get("max_iterations"), default=8),
            "max_tool_calls": first_defined(limits.get("max_tool_calls"), default=8),
            "max_llm_calls": first_defined(limits.get("max_llm_calls"), default=16),
            "max_failures": first_defined(limits.get("max_failures"), default=2),
            "max_runtime_seconds": (
                int(limits["timeout_ms"] / 1000) if limits.get("timeout_ms") else None
            ),
            "max_tokens_total": limits.get("max_tokens"),
            "max_cost": limits.get("budget"),
            "cost_currency": policies.get("cost_currency") or "USD",
            "rag_top_k": limits.get("rag_top_k") or 5,
            "rag_strategy": policies.get("rag_strategy") or "system_message",
            "memory_query": None,
            "memory_strategy": memory_strategy,
            "memory_top_k": memory_top_k,
            "context_window_messages": limits.get("context_window_messages"),
            "context_window_chars": limits.get("context_window_chars"),
            "verify": policies.get("verify") if policies.get("verify") is not None else True,
            "failure_strategy": policies.get("failure_strategy") or "respond",
            "thread_id": public_request.thread_id,
            "thread_title": public_request.input[:512],
            "request_id": public_request.request_id,
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

    def _build_runner(self, *, sandbox: bool = False) -> AgentService:
        async def execute_workflow_binding(workflow_ref: str, parameters: dict[str, Any]) -> dict[str, Any]:
            from app.modules.workflow.application.service import WorkflowService

            workflow_id = workflow_ref.split(":")[-1] if ":" in workflow_ref else workflow_ref
            workflow_service = WorkflowService(
                db=self.db,
                ctx=self.ctx,
                response_service=self.response_service,
                workflow_knowledge_query_port=self.workflow_knowledge_query_port,
            )
            return await workflow_service.execute_workflow(workflow_id, parameters or {})

        # A rehearsal answers tool calls without making them. The port is
        # swapped rather than the calls being skipped, so the agent still
        # decides to call, the decision is still recorded, and only the
        # outward effect is withheld.
        tool_port = SandboxToolPort(self.tool_port) if sandbox else self.tool_port

        return AgentService(
            db=self.db,
            ctx=self.ctx,
            llm_port=self.llm_port,
            tool_port=tool_port,
            tool_resolver=self.tool_resolver,
            memory_service=self.memory_service,
            response_service=self.response_service,
            trace_writer=self.trace_writer,
            workflow_executor=execute_workflow_binding,
            capability_catalog=self.capability_catalog,
            approval_checkpoint_gateway=self.approval_checkpoint_gateway,
        )

    def _resolve_thread_title(self, request: AgentRuntimeRequest) -> str | None:
        if request.thread_title:
            return request.thread_title
        for message in reversed(request.messages):
            if message.role == "user":
                return message.content[:120]
        return None

    @staticmethod
    def _current_user_message(request: AgentRuntimeRequest) -> ChatMessageInput:
        for message in reversed(request.messages):
            if message.role == "user":
                return message
        raise ValidationError("Agent turn requires one current user input")

    def _with_thread_history(
        self,
        request: AgentRuntimeRequest,
        thread: Any,
        current_message: ChatMessageInput,
        *,
        include_current: bool = True,
        head_message_id: str | None = None,
    ) -> AgentRuntimeRequest:
        """Rebuild trusted runtime history from the scoped thread ledger."""

        system_messages = [message for message in request.messages if message.role == "system"]
        history: list[ChatMessageInput] = []
        ledger_messages = self.thread_service.thread_repo.list_messages(thread.id)
        resolved_head_id = head_message_id or (ledger_messages[-1].id if ledger_messages else None)
        branch_messages = (
            self.thread_service.thread_repo.message_lineage(thread.id, resolved_head_id)
            if resolved_head_id
            else []
        )
        for message in branch_messages:
            if message.status != "completed" or message.role not in {
                "user",
                "assistant",
                "tool",
            }:
                continue
            if not message.content:
                continue
            history.append(
                ChatMessageInput(
                    role=message.role,
                    content=message.content,
                    metadata=message.metadata_json or None,
                )
            )
        return request.model_copy(
            update={
                "messages": [
                    *system_messages,
                    *history,
                    *([current_message] if include_current else []),
                ],
                "context_window_messages": (
                    request.context_window_messages or thread.max_history_messages
                ),
                "context_window_chars": (
                    request.context_window_chars or thread.max_history_chars
                ),
            }
        )

    def _response_input_payload(self, request: AgentRuntimeRequest, *, agent_version_id: str) -> dict[str, Any]:
        current_message = self._current_user_message(request)
        return {
            "input": current_message.content,
            "model": request.model_ref,
            "temperature": request.temperature,
            "thread_id": request.thread_id,
            "thread_title": request.thread_title,
            "agent_version_id": agent_version_id,
            "request_id": request.request_id,
            "source": "agent.execute",
        }

    def _response_output_payload(self, result: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "text": result.get("output") or "",
            "model": result.get("model"),
        }
        if result.get("citations"):
            payload["citations"] = result["citations"]
        if result.get("artifacts"):
            payload["artifacts"] = result["artifacts"]
        if result.get("finish_reason"):
            payload["finish_reason"] = result["finish_reason"]
        if result.get("iterations") is not None:
            payload["iterations"] = result["iterations"]
        if result.get("budget_exceeded"):
            payload["budget_exceeded"] = True
            payload["budget_reason"] = result.get("budget_reason")
        if result.get("reasoning"):
            payload["reasoning"] = result["reasoning"]
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

    @staticmethod
    def _persisted_message_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
        return {
            key: value
            for key, value in (metadata or {}).items()
            if key != "_attachment_context" and key != "_context_text"
        }

    def _run_artifact_descriptors(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(RunArtifact)
            .where(
                RunArtifact.run_id == run_id,
                RunArtifact.tenant_id == self.ctx.tenant_id,
                RunArtifact.workspace_id == self.ctx.workspace_id,
            )
            .order_by(RunArtifact.created_at)
        ).scalars()
        descriptors: list[dict[str, Any]] = []
        for artifact in rows:
            metadata = artifact.meta_json or {}
            descriptors.append(
                {
                    "id": artifact.id,
                    "type": artifact.type,
                    "name": metadata.get("name") or metadata.get("filename") or artifact.id,
                    "mime": artifact.mime,
                    "size_bytes": artifact.size_bytes,
                    "sha256": artifact.sha256,
                    "download_url": (
                        f"/api/v1/runs/{run_id}/artifacts/{artifact.id}/content"
                    ),
                }
            )
        return descriptors

    def _task_output_payload(
        self,
        result: dict[str, Any],
        *,
        response_id: str | None,
    ) -> dict[str, Any]:
        payload = {
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
            "artifacts": result.get("artifacts") or [],
            "branch_id": result.get("branch_id"),
        }
        if result.get("reasoning"):
            payload["reasoning"] = result["reasoning"]
        return payload

    def _assistant_message_metadata(
        self,
        agent: Agent,
        version: AgentVersion,
        result: dict[str, Any],
        *,
        response_id: str | None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
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
            "artifacts": result.get("artifacts") or [],
        }
        if result.get("reasoning"):
            metadata["reasoning"] = result["reasoning"]
        return metadata

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
        parent_message_id: str | None = None,
    ) -> None:
        metadata: dict[str, Any] = {
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
            content=error_message,
            run_id=run_id,
            task_id=task_id,
            response_id=response_id,
            parent_message_id=parent_message_id,
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
    async def capability_labels(self) -> dict[str, str]:
        """Public map of capability refs to display names."""
        return self._capability_name_map()

    def _capability_name_map(self) -> dict[str, str]:
        """Map capability refs to display names for binding labels."""
        items = [
            *self._model_capabilities(),
            *self._knowledge_capabilities(),
            *self._workflow_capabilities(),
            *self._tool_capabilities(),
            *self._plugin_artifact_capabilities(),
        ]
        mapping: dict[str, str] = {}
        for item in items:
            ref = item.get("ref")
            name = item.get("name")
            if ref and name:
                mapping.setdefault(str(ref), str(name))
        return mapping

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
        capability_names = self._capability_name_map()
        rows = [
            self._build_workbench_row(
                agent,
                runs_by_agent.get(agent.id, []),
                bindings_by_version.get(agent.published_version_id or "", []),
                capability_names,
            )
            for agent in agents
        ]
        owner_names = resolve_user_display_names(self.db, (row.owner for row in rows))
        for row in rows:
            if row.owner:
                row.owner = owner_names.get(row.owner, row.owner)
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
        capability_names: dict[str, str] | None = None,
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
                    label=(capability_names or {}).get(binding.target_key or "")
                    or binding.target_key
                    or binding.target_id
                    or binding.binding_type,
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
                self._INTERNAL_SANDBOX_KEY: True,
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
        messages = snapshot.get("messages")
        if isinstance(messages, list):
            candidates = [message for message in messages if isinstance(message, dict)]
            user_messages = [message for message in candidates if message.get("role") == "user"]
            selected = user_messages[-1] if user_messages else (candidates[-1] if candidates else None)
            if selected is not None:
                content = selected.get("content", "")
                if not isinstance(content, str):
                    content = json.dumps(content, ensure_ascii=False)
                return {"input": content}
        if snapshot.get("input_summary"):
            return {"input": str(snapshot["input_summary"])}
        if snapshot.get("input") is not None:
            content = snapshot["input"]
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
            return {"input": content}
        return {"input": json.dumps(snapshot, ensure_ascii=False)}

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
        sandbox = bool(inputs.pop(self._INTERNAL_SANDBOX_KEY, False))
        version_override_id = inputs.pop(self._INTERNAL_VERSION_OVERRIDE_KEY, None)
        if version_override_id:
            version = self._get_version(version_override_id)
            if version.agent_id != agent.id:
                raise NotFoundError(f"Version not found: {version_override_id}")
        else:
            version = self._resolve_execution_version(agent)
        request = self._request_from_version(version, inputs)
        current_message = self._current_user_message(request)
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

        ledger_messages = self.thread_service.thread_repo.list_messages(thread.id)
        user_parent_message_id = ledger_messages[-1].id if ledger_messages else None
        request = self._with_thread_history(
            request,
            thread,
            current_message,
            head_message_id=user_parent_message_id,
        )
        stored_user_message = self.thread_service.append_message(
            thread_id=thread.id,
            role="user",
            content=current_message.content,
            parent_message_id=user_parent_message_id,
            status="completed",
            metadata={
                **(current_message.metadata or {}),
                "request_id": request.request_id,
            },
        )

        run = self.trace_writer.create_run(
            mode="agent",
            kind="agent",
            subject_kind="agent",
            subject_id=agent.id,
            subject_version_id=version.id,
            input_summary=current_message.content[:8192],
            request_id=request.request_id,
            # Marked at creation so cost, dashboards and alerts can exclude a
            # rehearsal without having to work out afterwards what it was.
            sandbox=sandbox,
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
                "message_count": 1,
                "request_id": request.request_id,
            },
        )
        self.task_service.transition_task(
            task_id=task.id,
            status=TaskStatus.RUNNING.value,
            progress={"phase": "agent_loop"},
        )

        # Persist the execution snapshot before running so a retry has
        # something to replay. The "inline" status keeps the durable worker
        # from ever claiming this row: this attempt runs here, in-request.
        snapshot_interaction_id = generate_response_interaction_id()
        snapshot_interaction = ResponseInteraction(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            interaction_id=snapshot_interaction_id,
            parent_interaction_id=None,
            response_id=None,
            run_id=run.id,
            thread_id=thread.id,
            request_hash=snapshot_interaction_id,
            execution_json={
                "mode": "agent",
                "agent_id": agent.id,
                "agent_inputs": dict(inputs),
                "assistant_message_id": generate_thread_message_id(),
            },
            request_context_json=asdict(self.ctx),
            kind="run",
            status="inline",
            created_by=self.ctx.user_id,
        )
        self.db.add(snapshot_interaction)

        def _finalize_snapshot(status: str) -> None:
            snapshot_interaction.status = status
            snapshot_interaction.updated_at = utc_now()
            self.db.add(snapshot_interaction)

        if self.response_service:
            linked_response = self.response_service.create_linked_response(
                run_id=run.id,
                thread_id=thread.id,
                task_id=task.id,
                agent_id=agent.id,
                model=request.model_ref,
                request_id=request.request_id,
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

        # Publish the execution linkage before the first remote call so an explicit
        # cancellation request can resolve and close the active lifecycle.
        self.db.commit()

        request = request.model_copy(update={"task_id": task.id, "agent_id": agent.id})
        runner = self._build_runner(sandbox=sandbox)
        try:
            result = await runner.run(request, existing_run_id=run.id, response_id=linked_response.id if linked_response else None)
        except Exception as exc:
            if isinstance(exc, KernelError) and exc.code == "AGENT_RUN_CANCELED":
                _finalize_snapshot("canceled")
                if linked_response:
                    self.response_service.cancel_response(linked_response.id)
                self.task_service.cancel_task(task_id=task.id)
                raise
            logger.exception(
                "Agent execution failed",
                extra={"agent_id": agent.id, "run_id": run.id, "task_id": task.id},
            )
            _finalize_snapshot("failed")
            error_message = public_error_message(exc, _PUBLIC_AGENT_EXECUTION_ERROR)
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
                parent_message_id=stored_user_message.id,
            )
            self.task_service.transition_task(
                task_id=task.id,
                status=TaskStatus.FAILED.value,
                error_code="agent_execution_failed",
                error_message=error_message,
            )
            raise

        response_id = linked_response.id if linked_response else None
        if result.get("status") == TaskStatus.WAITING_APPROVAL.value:
            # Deliberately left "inline": the attempt is still in flight through
            # approval, and "waiting_approval" would collide with the resume
            # claim that targets durable worker interactions in that status.
            current_task = self.task_service.get_task(task.id)
            if current_task.status != TaskStatus.WAITING_APPROVAL.value:
                self.task_service.transition_task(
                    task_id=task.id,
                    status=TaskStatus.WAITING_APPROVAL.value,
                    progress={"phase": "approval", "interrupt": result.get("interrupt")},
                )
            self.thread_service.thread_repo.touch_thread(thread, latest_run_id=result.get("run_id"))
            return {
                **result,
                "thread_id": thread.id,
                "task_id": task.id,
                "response_id": response_id,
                "request_id": request.request_id,
            }

        _finalize_snapshot("succeeded")
        result = {
            **result,
            "artifacts": self._run_artifact_descriptors(run.id),
        }
        self.thread_service.append_message(
            thread_id=thread.id,
            role="assistant",
            content=result.get("output") or "",
            run_id=result.get("run_id"),
            task_id=task.id,
            response_id=response_id,
            parent_message_id=stored_user_message.id,
            status="completed",
            model_ref=result.get("model"),
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
            "request_id": request.request_id,
        }

    @rbac_guard(RESOURCE_AGENT, "run", resource_id_arg="agent_id")
    async def cancel_agent_execution(self, agent_id: str, run_id: str) -> dict[str, Any]:
        """Explicitly close the Run, Task, and Response lifecycle for one execution."""

        self._get_agent(agent_id)
        run = self.db.get(Run, run_id)
        if (
            run is None
            or run.tenant_id != self.ctx.tenant_id
            or run.workspace_id != self.ctx.workspace_id
            or run.subject_kind != "agent"
            or run.subject_id != agent_id
        ):
            raise NotFoundError(f"Agent run not found: {run_id}")

        responses = (
            self.response_service.response_repo.list_for_run(run_id)
            if self.response_service is not None
            else []
        )
        for response in responses:
            self.response_service.cancel_response(response.id)
        if run.status not in {"succeeded", "failed", "canceled", "expired"}:
            self.trace_writer.update_run_status(
                run.id,
                "canceled",
                output_summary="Agent execution canceled",
                error_code="agent_run_canceled",
                error_message="Agent execution was explicitly canceled",
            )

        tasks = list(
            self.db.execute(
                select(Task).where(
                    Task.tenant_id == self.ctx.tenant_id,
                    Task.workspace_id == self.ctx.workspace_id,
                    Task.run_id == run_id,
                )
            ).scalars()
        )
        for task in tasks:
            self.task_service.cancel_task(task_id=task.id)
        self.db.refresh(run)
        return {
            "run_id": run.id,
            "status": run.status,
            "task_ids": [task.id for task in tasks],
            "response_ids": [response.id for response in responses],
        }

    @rbac_guard(RESOURCE_AGENT, "run", resource_id_arg="agent_id")
    async def execute_agent_streaming(
        self,
        agent_id: str,
        inputs: dict[str, Any],
        event_emitter: EventEmitter,
        on_response_started: Callable[[Response, ResponseService], Awaitable[None]] | None = None,
        response_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute agent with event streaming via the provided emitter.

        Same lifecycle as execute_agent but passes event_emitter to the runner
        so callers can observe events in real time (e.g. SSE).
        """
        agent = self._get_agent(agent_id)
        internal_inputs = dict(inputs)
        attachments = list(internal_inputs.pop("_attachments", []) or [])
        attachment_context = list(internal_inputs.pop("_attachment_context", []) or [])
        attachment_ids = list(internal_inputs.pop("_attachment_ids", []) or [])
        agui_context = dict(internal_inputs.pop("_agui_context", {}) or {})
        agui_options = dict(internal_inputs.pop("_agui_options", {}) or {})
        approval_responses = list(internal_inputs.pop("_agui_resume", []) or [])
        resume_execution = internal_inputs.pop("_resume_execution", None)
        if resume_execution:
            run = self.db.get(Run, str(resume_execution.get("run_id") or ""))
            if (
                run is None
                or run.tenant_id != self.ctx.tenant_id
                or run.workspace_id != self.ctx.workspace_id
                or run.subject_id != agent.id
            ):
                raise NotFoundError("Approval execution run not found")
            version = self._get_version(str(run.subject_version_id or ""))
        else:
            version = self._resolve_execution_version(agent)
        request_updates: dict[str, Any] = {
            "approval_responses": approval_responses,
            "show_reasoning": bool(agui_options.get("show_reasoning")),
        }
        reasoning_effort = agui_options.get("reasoning_effort")
        if isinstance(reasoning_effort, str) and reasoning_effort:
            request_updates["reasoning_effort"] = reasoning_effort
        request = self._request_from_version(version, internal_inputs).model_copy(
            update=request_updates
        )
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

        if attachment_ids:
            if self.attachment_service is None:
                raise ValidationError("Attachment resolution is not configured")
            resolved_attachments = await self.attachment_service.resolve_for_message(
                attachment_ids,
                thread_id=thread.id,
            )
            attachments = [
                {
                    key: value
                    for key, value in item.items()
                    if not key.startswith("_")
                }
                for item in resolved_attachments
            ]
            attachment_context = [
                {
                    "id": str(item.get("id") or ""),
                    "name": str(item.get("name") or item.get("filename") or "attachment"),
                    "text": str(item.get("_context_text") or ""),
                }
                for item in resolved_attachments
                if item.get("_context_text")
            ]

        if attachments or attachment_context:
            messages = list(request.messages)
            for index in range(len(messages) - 1, -1, -1):
                message = messages[index]
                if message.role != "user":
                    continue
                metadata = dict(message.metadata or {})
                metadata["attachments"] = attachments
                metadata["_attachment_context"] = attachment_context
                messages[index] = message.model_copy(update={"metadata": metadata})
                break
            request = request.model_copy(update={"messages": messages})

        current_message = self._current_user_message(request)

        agui_message_id = str(agui_context.get("message_id") or "")
        existing_user_message = (
            self.thread_service.thread_repo.get_message(thread.id, agui_message_id)
            if agui_message_id
            else None
        )
        if existing_user_message is None and agui_message_id:
            existing_user_message = next(
                (
                    message
                    for message in self.thread_service.thread_repo.list_messages(thread.id)
                    if (message.metadata_json or {}).get("agui_message_id") == agui_message_id
                ),
                None,
            )
        if existing_user_message is not None and existing_user_message.role != "user":
            raise ValidationError("AG-UI message reuse requires an existing user message")
        ledger_messages = self.thread_service.thread_repo.list_messages(thread.id)
        requested_parent_id = agui_context.get("parent_message_id")
        if requested_parent_id is not None and not isinstance(requested_parent_id, str):
            raise ValidationError("AG-UI parent message ID must be a string")
        user_parent_message_id = (
            existing_user_message.parent_message_id
            if existing_user_message is not None
            else requested_parent_id or (ledger_messages[-1].id if ledger_messages else None)
        )
        current_user_message_id = (
            existing_user_message.id if existing_user_message is not None else None
        )
        history_head_message_id = (
            existing_user_message.id if existing_user_message is not None else user_parent_message_id
        )
        request = self._with_thread_history(
            request,
            thread,
            current_message,
            include_current=not bool(resume_execution) and existing_user_message is None,
            head_message_id=history_head_message_id,
        )
        if resume_execution:
            task = self.task_service.get_task(str(resume_execution.get("task_id") or ""))
            if task.run_id != run.id or task.agent_id != agent.id or task.thread_id != thread.id:
                raise ValidationError("Approval resume resources do not belong to the Agent run")
            approval_checkpoint = (task.progress_json or {}).get("checkpoint")
            if not isinstance(approval_checkpoint, dict):
                raise ValidationError("Agent approval run has no durable checkpoint")
            if task.status == TaskStatus.WAITING_APPROVAL.value:
                task = self.task_service.resume_task(task_id=task.id)
            elif task.status != TaskStatus.RUNNING.value:
                raise ValidationError(f"Agent approval run cannot resume from task status {task.status}")
            self.trace_writer.update_run_status(run.id, "running")
            if self.response_service:
                linked_response = self.response_service.get_response(
                    str(resume_execution.get("response_id") or "")
                )
                if (
                    linked_response.run_id != run.id
                    or linked_response.task_id != task.id
                    or linked_response.thread_id != thread.id
                    or linked_response.agent_id != agent.id
                ):
                    raise ValidationError("Approval resume response does not belong to the Agent run")
                linked_response = self.response_service.mark_running(linked_response)
        else:
            if existing_user_message is None:
                stored_user_message = self.thread_service.append_message(
                    thread_id=thread.id,
                    role="user",
                    content=current_message.content,
                    parent_message_id=user_parent_message_id,
                    status="completed",
                    metadata={
                        **self._persisted_message_metadata(current_message.metadata),
                        "request_id": request.request_id,
                        "branch_id": agui_context.get("branch_id"),
                        "agui_message_id": agui_message_id or None,
                    },
                )
                current_user_message_id = stored_user_message.id

            run = self.trace_writer.create_run(
                mode="agent",
                kind="agent",
                subject_kind="agent",
                subject_id=agent.id,
                subject_version_id=version.id,
                input_summary=current_message.content[:8192],
                request_id=request.request_id,
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
                    "message_count": 1,
                    "request_id": request.request_id,
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
                    request_id=request.request_id,
                    input_json=self._response_input_payload(request, agent_version_id=version.id),
                    metadata_json={
                        "source": "agent.stream",
                        "agent_id": agent.id,
                        "agent_version_id": version.id,
                        "thread_id": thread.id,
                        "task_id": task.id,
                        **(response_metadata or {}),
                    },
                    emit_initial_events=on_response_started is None,
                )
                linked_response = self.response_service.mark_running(linked_response)

        # The detached stream uses a worker session. Commit its execution linkage
        # before remote calls so the cancel endpoint can observe it immediately.
        self.db.commit()
        if linked_response is not None and on_response_started is not None:
            await on_response_started(linked_response, self.response_service)

        request_update: dict[str, Any] = {"task_id": task.id, "agent_id": agent.id}
        if resume_execution:
            request_update["approval_checkpoint"] = approval_checkpoint
        request = request.model_copy(update=request_update)
        runner = self._build_runner()
        try:
            result = await runner.run(
                request,
                existing_run_id=run.id,
                response_id=linked_response.id if linked_response else None,
                event_emitter=event_emitter,
                emit_response_events=on_response_started is None,
            )
        except Exception as exc:
            if isinstance(exc, KernelError) and exc.code == "AGENT_RUN_CANCELED":
                if linked_response:
                    self.response_service.cancel_response(
                        linked_response.id,
                        emit_event=on_response_started is None,
                    )
                self.task_service.cancel_task(task_id=task.id)
                raise
            logger.exception(
                "Agent streaming execution failed",
                extra={"agent_id": agent.id, "run_id": run.id, "task_id": task.id},
            )
            error_message = public_error_message(exc, _PUBLIC_AGENT_EXECUTION_ERROR)
            if linked_response:
                linked_response = self.response_service.fail_response(
                    response=linked_response,
                    error_code="agent_execution_failed",
                    error_message=error_message,
                    source="agent",
                    failed_event_type=None if on_response_started is not None else "response.failed",
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
                parent_message_id=current_user_message_id,
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
        if result.get("status") == TaskStatus.WAITING_APPROVAL.value:
            current_task = self.task_service.get_task(task.id)
            if current_task.status != TaskStatus.WAITING_APPROVAL.value:
                self.task_service.transition_task(
                    task_id=task.id,
                    status=TaskStatus.WAITING_APPROVAL.value,
                    progress={
                        "phase": "approval",
                        "interrupt": result.get("interrupt"),
                        "checkpoint": result.get("checkpoint"),
                    },
                )
            self.thread_service.thread_repo.touch_thread(thread, latest_run_id=result.get("run_id"))
            return {
                **result,
                "thread_id": thread.id,
                "task_id": task.id,
                "response_id": response_id,
                "request_id": request.request_id,
            }

        result = {
            **result,
            "artifacts": self._run_artifact_descriptors(run.id),
            "branch_id": agui_context.get("branch_id"),
        }
        self.thread_service.append_message(
            thread_id=thread.id,
            message_id=(
                str(agui_context.get("assistant_message_id"))
                if agui_context.get("assistant_message_id")
                else None
            ),
            role="assistant",
            content=result.get("output") or "",
            run_id=result.get("run_id"),
            task_id=task.id,
            response_id=response_id,
            parent_message_id=current_user_message_id,
            status="completed",
            model_ref=result.get("model"),
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
                output_event_type=None if on_response_started is not None else "response.output_text.done",
                completed_event_type=None if on_response_started is not None else "response.succeeded",
            )
        return {
            **result,
            "thread_id": thread.id,
            "task_id": task.id,
            "response_id": response_id,
            "request_id": request.request_id,
        }
