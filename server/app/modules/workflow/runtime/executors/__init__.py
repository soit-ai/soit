""" executors

Workflow node executors.
"""

from app.modules.workflow.runtime.executors.base import NodeExecutor
from app.modules.workflow.runtime.executors.condition import ConditionNodeExecutor
from app.modules.workflow.runtime.executors.http import HttpNodeExecutor
from app.modules.workflow.runtime.executors.input import InputNodeExecutor
from app.modules.workflow.runtime.executors.llm import LLMNodeExecutor
from app.modules.workflow.runtime.executors.node import RegistryNodeExecutor
from app.modules.workflow.runtime.executors.output import OutputNodeExecutor
from app.modules.workflow.runtime.executors.retrieve import RetrieveNodeExecutor
from app.modules.workflow.runtime.executors.set_var import SetVarNodeExecutor
from app.modules.workflow.runtime.executors.tool import ToolNodeExecutor
from app.modules.workflow.runtime.executors.transform import TransformNodeExecutor

# Registry for node executors
_executor_registry: dict[str, type[NodeExecutor]] = {}


def register_executor(node_type: str, executor_class: type[NodeExecutor]) -> None:
    """Register a node executor.

    Args:
        node_type: Node type (e.g., "llm", "retrieve").
        executor_class: Executor class.
    """
    _executor_registry[node_type] = executor_class


def get_executor(node_type: str) -> type[NodeExecutor]:
    """Get executor class for node type.

    Args:
        node_type: Node type.

    Returns:
        Executor class.

    Raises:
        ValueError: If executor not found.
    """
    executor_class = _executor_registry.get(node_type)
    if not executor_class:
        raise ValueError(f"No executor registered for node type: {node_type}")
    return executor_class


# Register default executors
register_executor("input", InputNodeExecutor)
register_executor("llm", LLMNodeExecutor)
register_executor("retrieve", RetrieveNodeExecutor)
register_executor("tool", ToolNodeExecutor)
register_executor("condition", ConditionNodeExecutor)
register_executor("transform", TransformNodeExecutor)
register_executor("set_var", SetVarNodeExecutor)
register_executor("http", HttpNodeExecutor)
register_executor("output", OutputNodeExecutor)
register_executor("node", RegistryNodeExecutor)
