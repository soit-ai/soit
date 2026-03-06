""" base

Base node executor interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Set

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import LLMPort
from app.kernel.ports.tools.interface import ToolPort
from app.kernel.ports.vector.interface import VectorPort
from app.kernel.ports.plugins.interface import PluginRuntimePort
from app.kernel.trace.writer import TraceWriter
from app.modules.workflow.application.variable_resolver import VariableResolver


class ExecutionContext:
    """Execution context for node executors."""
    
    def __init__(
        self,
        run_id: str,
        step_id: str,
        ctx: RequestContext,
        trace_writer: TraceWriter,
        llm_port: Optional[LLMPort] = None,
        tool_port: Optional[ToolPort] = None,
        vector_port: Optional[VectorPort] = None,
        plugin_runtime_port: Optional[PluginRuntimePort] = None,
        workflow_policy: Optional[Dict[str, Any]] = None,
        steps_outputs: Optional[Dict[str, Dict[str, Any]]] = None,
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
            workflow_policy: Optional workflow policy object.
            steps_outputs: Dictionary of step outputs.
        """
        self.run_id = run_id
        self.step_id = step_id
        self.ctx = ctx
        self.trace_writer = trace_writer
        self.llm_port = llm_port
        self.tool_port = tool_port
        self.vector_port = vector_port
        self.plugin_runtime_port = plugin_runtime_port
        self.workflow_policy = workflow_policy or {}
        self.steps_outputs = steps_outputs or {}


class NodeExecutor(ABC):
    """Base class for node executors."""
    
    @abstractmethod
    async def execute(
        self,
        node: Dict[str, Any],
        context: ExecutionContext,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
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
        node: Dict[str, Any],
        workflow_inputs: Dict[str, Any],
        steps_outputs: Dict[str, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        skipped_steps: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
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
