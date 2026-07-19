""" base

Base node executor interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import LLMPort
from app.kernel.ports.plugins.interface import PluginRuntimePort
from app.kernel.ports.tools.interface import ToolPort
from app.kernel.ports.vector.interface import VectorPort
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.workflow.application.variable_resolver import VariableResolver

if TYPE_CHECKING:
    from app.modules.workflow.application.contracts import WorkflowKnowledgeQueryPort


class ExecutionContext:
    """Execution context for node executors."""

    def __init__(
        self,
        run_id: str,
        step_id: str,
        ctx: RequestContext,
        trace_writer: TraceWriter,
        llm_port: LLMPort | None = None,
        tool_port: ToolPort | None = None,
        vector_port: VectorPort | None = None,
        workflow_knowledge_query_port: WorkflowKnowledgeQueryPort | None = None,
        plugin_runtime_port: PluginRuntimePort | None = None,
        response_service: ResponseService | None = None,
        workflow_policy: dict[str, Any] | None = None,
        steps_outputs: dict[str, dict[str, Any]] | None = None,
        workflow_run_id: str | None = None,
        approval_checkpoint_gateway: Any | None = None,
        task_id: str | None = None,
        thread_id: str | None = None,
        agent_id: str | None = None,
        resume_approval_node_id: str | None = None,
        resume_tool_call_id: str | None = None,
        resume_tool_run_step_id: str | None = None,
        resume_response_id: str | None = None,
        workflow_inputs: dict[str, Any] | None = None,
    ):
        """Initialize execution context.

        Args:
            run_id: Run ID.
            step_id: Step ID.
            ctx: Request context.
            trace_writer: Trace writer.
            llm_port: Optional LLM gateway.
            tool_port: Optional tool gateway.
            vector_port: Optional vector gateway.
            workflow_knowledge_query_port: Optional scoped knowledge query port.
            workflow_policy: Optional workflow policy object.
            steps_outputs: Dictionary of step outputs.
            workflow_run_id: Optional aggregate id for workflow_runs outbox (B3).
            approval_checkpoint_gateway: Optional Enterprise approval checkpoint gateway.
            task_id: Optional runtime task id for checkpoint pause integration.
            thread_id: Optional runtime thread id for checkpoint context.
            agent_id: Optional agent id for checkpoint context.
            workflow_inputs: Validated workflow invocation payload.
        """
        self.run_id = run_id
        self.step_id = step_id
        self.ctx = ctx
        self.trace_writer = trace_writer
        self.llm_port = llm_port
        self.tool_port = tool_port
        self.vector_port = vector_port
        self.workflow_knowledge_query_port = workflow_knowledge_query_port
        self.plugin_runtime_port = plugin_runtime_port
        self.response_service = response_service
        self.workflow_policy = workflow_policy or {}
        self.workflow_inputs = dict(workflow_inputs or {})
        self.steps_outputs = steps_outputs or {}
        self.workflow_run_id = workflow_run_id
        self.approval_checkpoint_gateway = approval_checkpoint_gateway
        self.task_id = task_id
        self.thread_id = thread_id
        self.agent_id = agent_id
        self.resume_approval_node_id = resume_approval_node_id
        self.resume_tool_call_id = resume_tool_call_id
        self.resume_tool_run_step_id = resume_tool_run_step_id
        self.resume_response_id = resume_response_id


class NodeExecutor(ABC):
    """Base class for node executors."""

    @abstractmethod
    async def execute(
        self,
        node: dict[str, Any],
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a workflow node.

        Args:
            node: Node definition from WorkflowSpec.
            context: Execution context.
            inputs: Resolved node inputs.

        Returns:
            Node output dictionary.
        """
        pass

    def resolve_inputs(
        self,
        node: dict[str, Any],
        workflow_inputs: dict[str, Any],
        steps_outputs: dict[str, dict[str, Any]],
        context: dict[str, Any] | None = None,
        skipped_steps: set[str] | None = None,
    ) -> dict[str, Any]:
        """Resolve node inputs using variable resolver.

        Args:
            node: Node definition.
            workflow_inputs: Workflow inputs.
            steps_outputs: Step outputs.

        Returns:
            Resolved inputs dictionary.
        """
        resolver = VariableResolver(
            workflow_inputs,
            steps_outputs,
            context=context,
            skipped_steps=skipped_steps,
        )
        node_input = node.get("input", {})
        return resolver.resolve(node_input)
