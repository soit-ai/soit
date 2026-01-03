""" compiler

WorkflowSpec -> ExecutionPlan compiler.
"""

from typing import Dict, Any, List, Set, Optional
from collections import defaultdict, deque

from app.kernel.specs.validator import validator
from app.kernel.contracts.execution_plan import ExecutionPlan, StepPlan
from app.kernel.commons.errors import ValidationError
from app.modules.workflow.application.variable_resolver import VariableResolver


class WorkflowCompiler:
    """Compile WorkflowSpec to ExecutionPlan."""
    
    def __init__(self):
        """Initialize workflow compiler."""
        pass
    
    def compile(
        self,
        workflow_spec: Dict[str, Any],
        inputs: Dict[str, Any],
        run_id: str,
    ) -> ExecutionPlan:
        """Compile WorkflowSpec to ExecutionPlan.
        
        Args:
            workflow_spec: WorkflowSpec dictionary.
            inputs: Workflow inputs.
            run_id: Run ID for execution plan.
            
        Returns:
            ExecutionPlan instance.
            
        Raises:
            ValidationError: If spec is invalid or has cycles.
        """
        # Validate spec
        validator.validate_workflow_spec(workflow_spec)
        
        # Build DAG
        nodes = {node["id"]: node for node in workflow_spec["nodes"]}
        edges = workflow_spec.get("edges", [])
        
        # Build graph structure
        graph = self._build_graph(nodes, edges)
        
        # Check for cycles
        if self._has_cycle(graph, nodes):
            raise ValidationError("Workflow contains cycles")
        
        # Check for isolated nodes
        isolated = self._find_isolated_nodes(graph, nodes)
        if isolated:
            raise ValidationError(f"Isolated nodes found: {isolated}")
        
        # Topological sort
        execution_order = self._topological_sort(graph, nodes)
        
        # Generate step plans
        step_plans = []
        for node_id in execution_order:
            node = nodes[node_id]
            step_plan = StepPlan(
                step_id=f"st_{node_id}",
                step_type=node["type"],
                node_id=node_id,
                input_data=node.get("input", {}),
                config={
                    "timeout_ms": node.get("timeout_ms"),
                    "retry_policy": node.get("retry_policy"),
                },
            )
            step_plans.append(step_plan)
        
        # Build execution plan
        plan_data = {
            "nodes": nodes,
            "edges": edges,
            "execution_order": execution_order,
            "semantics": workflow_spec.get("semantics", {}),
        }
        
        return ExecutionPlan(
            run_id=run_id,
            mode="workflow",
            plan_data=plan_data,
            inputs=inputs,
        )
    
    def _build_graph(
        self,
        nodes: Dict[str, Dict[str, Any]],
        edges: List[Dict[str, str]],
    ) -> Dict[str, List[str]]:
        """Build graph structure from nodes and edges.
        
        Args:
            nodes: Dictionary mapping node_id to node.
            edges: List of edge dictionaries.
            
        Returns:
            Dictionary mapping node_id to list of successor node_ids.
        """
        graph = defaultdict(list)
        
        for edge in edges:
            from_id = edge["from"]
            to_id = edge["to"]
            
            if from_id not in nodes or to_id not in nodes:
                raise ValidationError(f"Edge references unknown node: {from_id} -> {to_id}")
            
            graph[from_id].append(to_id)
        
        return dict(graph)
    
    def _has_cycle(self, graph: Dict[str, List[str]], nodes: Dict[str, Dict[str, Any]]) -> bool:
        """Check if graph has cycles using DFS.
        
        Args:
            graph: Graph structure.
            nodes: Dictionary of nodes.
            
        Returns:
            True if cycle exists.
        """
        visited = set()
        rec_stack = set()
        
        def dfs(node_id: str) -> bool:
            if node_id in rec_stack:
                return True  # Cycle found
            if node_id in visited:
                return False
            
            visited.add(node_id)
            rec_stack.add(node_id)
            
            for neighbor in graph.get(node_id, []):
                if dfs(neighbor):
                    return True
            
            rec_stack.remove(node_id)
            return False
        
        for node_id in nodes:
            if node_id not in visited:
                if dfs(node_id):
                    return True
        
        return False
    
    def _find_isolated_nodes(
        self,
        graph: Dict[str, List[str]],
        nodes: Dict[str, Dict[str, Any]],
    ) -> List[str]:
        """Find isolated nodes (no incoming or outgoing edges).
        
        Args:
            graph: Graph structure.
            nodes: Dictionary of nodes.
            
        Returns:
            List of isolated node IDs.
        """
        # Build reverse graph (incoming edges)
        reverse_graph = defaultdict(list)
        for from_id, to_ids in graph.items():
            for to_id in to_ids:
                reverse_graph[to_id].append(from_id)
        
        isolated = []
        for node_id in nodes:
            has_incoming = node_id in reverse_graph and len(reverse_graph[node_id]) > 0
            has_outgoing = node_id in graph and len(graph[node_id]) > 0
            
            if not has_incoming and not has_outgoing:
                isolated.append(node_id)
        
        return isolated
    
    def _topological_sort(
        self,
        graph: Dict[str, List[str]],
        nodes: Dict[str, Dict[str, Any]],
    ) -> List[str]:
        """Topological sort using Kahn's algorithm.
        
        Args:
            graph: Graph structure.
            nodes: Dictionary of nodes.
            
        Returns:
            List of node IDs in topological order.
        """
        # Build in-degree map
        in_degree = {node_id: 0 for node_id in nodes}
        for from_id, to_ids in graph.items():
            for to_id in to_ids:
                in_degree[to_id] += 1
        
        # Find nodes with no incoming edges
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        result = []
        
        while queue:
            node_id = queue.popleft()
            result.append(node_id)
            
            # Remove edges from this node
            for neighbor in graph.get(node_id, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Check if all nodes were processed
        if len(result) != len(nodes):
            raise ValidationError("Graph has cycles or disconnected components")
        
        return result
