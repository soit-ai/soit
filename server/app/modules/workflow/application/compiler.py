""" compiler

WorkflowSpec -> ExecutionPlan compiler.
"""

from collections import defaultdict, deque
from typing import Any

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.execution_plan import ExecutionPlan, StepPlan
from app.kernel.specs.validator import validator


class WorkflowCompiler:
    """Compile WorkflowSpec to ExecutionPlan."""

    def __init__(self):
        """Initialize workflow compiler."""
        self.validator = validator

    def compile(
        self,
        workflow_spec: dict[str, Any],
        inputs: dict[str, Any],
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
        self.validator.validate_workflow_spec(workflow_spec)

        # Build DAG from canonical graph
        graph = workflow_spec.get("graph") or {}
        nodes_list = graph.get("nodes") or []
        edges = graph.get("edges") or []
        nodes = {node["id"]: self._normalize_node(node) for node in nodes_list}

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
            "edges": self._normalize_edges(edges),
            "execution_order": execution_order,
            "semantics": workflow_spec.get("semantics", {}),
            "policy": workflow_spec.get("policy", {}),
        }

        return ExecutionPlan(
            run_id=run_id,
            mode="workflow",
            plan_data=plan_data,
            inputs=inputs,
        )

    def _build_graph(
        self,
        nodes: dict[str, dict[str, Any]],
        edges: list[dict[str, str]],
    ) -> dict[str, list[str]]:
        """Build graph structure from nodes and edges.

        Args:
            nodes: Dictionary mapping node_id to node.
            edges: List of edge dictionaries.

        Returns:
            Dictionary mapping node_id to list of successor node_ids.
        """
        graph = defaultdict(list)

        for edge in edges:
            from_id = edge.get("from")
            to_id = edge.get("to")

            if from_id not in nodes or to_id not in nodes:
                raise ValidationError(f"Edge references unknown node: {from_id} -> {to_id}")

            graph[from_id].append(to_id)

        return dict(graph)

    def _has_cycle(self, graph: dict[str, list[str]], nodes: dict[str, dict[str, Any]]) -> bool:
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
        graph: dict[str, list[str]],
        nodes: dict[str, dict[str, Any]],
    ) -> list[str]:
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
        graph: dict[str, list[str]],
        nodes: dict[str, dict[str, Any]],
    ) -> list[str]:
        """Topological sort using Kahn's algorithm.

        Args:
            graph: Graph structure.
            nodes: Dictionary of nodes.

        Returns:
            List of node IDs in topological order.
        """
        # Build in-degree map
        in_degree = dict.fromkeys(nodes, 0)
        for _from_id, to_ids in graph.items():
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

    def _normalize_node(self, node: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(node)
        params = node.get("params")
        if params is None and "input" in node:
            params = node.get("input")
        normalized["input"] = params or {}
        normalized.setdefault("type", node.get("type"))
        return normalized

    def _normalize_edges(self, edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for edge in edges:
            normalized = dict(edge)
            if "when" not in normalized and "condition" in normalized:
                normalized["when"] = normalized.get("condition")
            out.append(normalized)
        return out
