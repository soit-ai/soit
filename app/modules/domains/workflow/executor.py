""" executor

DAG execution engine for workflows.
"""

import asyncio
from typing import Dict, Any, List, Set, Optional
from collections import defaultdict, deque

from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.execution.engine import ExecutionEngine
from app.modules.domains.workflow.executors import get_executor
from app.modules.domains.workflow.executors.base import ExecutionContext
from app.modules.domains.workflow.variable_resolver import VariableResolver
from app.kernel.commons.errors import ValidationError


class WorkflowExecutor:
    """DAG execution engine for workflows."""
    
    def __init__(self, execution_engine: ExecutionEngine):
        """Initialize workflow executor.
        
        Args:
            execution_engine: Execution engine instance.
        """
        self.execution_engine = execution_engine
    
    async def execute(
        self,
        plan: ExecutionPlan,
        context: ExecutionContext,
    ) -> Dict[str, Any]:
        """Execute workflow DAG.
        
        Args:
            plan: Execution plan.
            context: Execution context.
            
        Returns:
            Final output dictionary.
        """
        nodes = plan.plan_data["nodes"]
        edges = plan.plan_data["edges"]
        execution_order = plan.plan_data["execution_order"]
        semantics = plan.plan_data.get("semantics", {})
        
        # Build graph for dependency tracking
        graph = self._build_graph(edges)
        reverse_graph = self._build_reverse_graph(edges)
        
        # Track node states and outputs
        node_states: Dict[str, str] = {}  # node_id -> status
        node_outputs: Dict[str, Dict[str, Any]] = {}  # node_id -> output
        in_degree = {node_id: len(reverse_graph.get(node_id, [])) for node_id in nodes}
        
        # Execution queue (nodes ready to execute)
        ready_queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        
        # Execute nodes in topological order with concurrency
        concurrency = semantics.get("concurrency", 1)
        semaphore = asyncio.Semaphore(concurrency)
        
        async def execute_node(node_id: str):
            """Execute a single node."""
            async with semaphore:
                node = nodes[node_id]
                node_type = node["type"]
                step_id = f"st_{node_id}"
                
                # Get executor
                executor_class = get_executor(node_type)
                executor = executor_class()
                
                # Resolve inputs
                # Build steps_outputs mapping: node_id -> output
                steps_outputs_map = {}
                for nid in execution_order:
                    if nid in node_outputs:
                        steps_outputs_map[nid] = node_outputs[nid]
                
                resolver = VariableResolver(plan.inputs, steps_outputs_map)
                inputs = resolver.resolve(node.get("input", {}))
                
                # Create RunStep for tracking
                run_step = context.trace_writer.create_step(
                    run_id=context.run_id,
                    step_type=node_type,
                    step_id=step_id,
                    node_id=node_id,
                    input_summary=str(inputs)[:8192] if inputs else None,
                )
                
                # Update step status to running
                context.trace_writer.update_step_status(
                    run_step.id,
                    status="running",
                )
                
                # Create step context
                step_context = ExecutionContext(
                    run_id=context.run_id,
                    step_id=step_id,
                    ctx=context.ctx,
                    trace_writer=context.trace_writer,
                    llm_gateway=context.llm_gateway,
                    tool_gateway=context.tool_gateway,
                    vector_gateway=context.vector_gateway,
                    steps_outputs=node_outputs,
                )
                
                try:
                    # Execute node
                    output = await executor.execute(node, step_context, inputs)
                    node_outputs[node_id] = output
                    node_states[node_id] = "succeeded"
                    
                    # Update step status to succeeded
                    context.trace_writer.update_step_status(
                        run_step.id,
                        status="succeeded",
                        output_summary=str(output)[:8192] if output else None,
                    )
                    
                    # Update in-degree for dependent nodes
                    for dependent_id in graph.get(node_id, []):
                        in_degree[dependent_id] -= 1
                        if in_degree[dependent_id] == 0:
                            ready_queue.append(dependent_id)
                
                except Exception as e:
                    node_states[node_id] = "failed"
                    
                    # Update step status to failed
                    error_message = str(e)
                    context.trace_writer.update_step_status(
                        run_step.id,
                        status="failed",
                        output_summary=error_message[:8192],
                        error_code="NODE_EXECUTION_ERROR",
                        error_message=error_message,
                        error_details={"node_id": node_id, "node_type": node_type},
                    )
                    
                    error_strategy = semantics.get("on_error", "fail_fast")
                    
                    if error_strategy == "fail_fast":
                        raise ValidationError(f"Node {node_id} failed: {error_message}")
                    elif error_strategy == "continue":
                        # Continue execution, mark node as failed
                        node_outputs[node_id] = {"error": error_message}
                    # "compensate" strategy not implemented yet
        
        # Execute all nodes
        tasks = []
        while ready_queue or tasks:
            # Start new tasks for ready nodes
            while ready_queue and len(tasks) < concurrency:
                node_id = ready_queue.popleft()
                tasks.append(asyncio.create_task(execute_node(node_id)))
            
            # Wait for at least one task to complete
            if tasks:
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                tasks = list(pending)
                
                # Check for exceptions
                for task in done:
                    try:
                        await task
                    except Exception as e:
                        # If fail_fast, propagate exception
                        if semantics.get("on_error") == "fail_fast":
                            raise
                        # Otherwise, continue
        
        # Find output node
        output_node_id = None
        for node_id, node in nodes.items():
            if node["type"] == "output":
                output_node_id = node_id
                break
        
        if output_node_id and output_node_id in node_outputs:
            return node_outputs[output_node_id]
        
        # If no output node, return last node's output
        if execution_order and execution_order[-1] in node_outputs:
            return node_outputs[execution_order[-1]]
        
        return {}
    
    def _build_graph(self, edges: List[Dict[str, str]]) -> Dict[str, List[str]]:
        """Build forward graph (from -> to)."""
        graph = defaultdict(list)
        for edge in edges:
            graph[edge["from"]].append(edge["to"])
        return dict(graph)
    
    def _build_reverse_graph(self, edges: List[Dict[str, str]]) -> Dict[str, List[str]]:
        """Build reverse graph (to -> from)."""
        graph = defaultdict(list)
        for edge in edges:
            graph[edge["to"]].append(edge["from"])
        return dict(graph)

