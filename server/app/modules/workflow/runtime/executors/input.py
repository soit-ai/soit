"""Input workflow node executor."""

from __future__ import annotations

from typing import Any

from app.modules.workflow.runtime.executors.base import ExecutionContext, NodeExecutor


class InputNodeExecutor(NodeExecutor):
    """Expose the already validated workflow invocation payload."""

    async def execute(
        self,
        node: dict[str, Any],
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        payload = dict(context.workflow_inputs or {})
        selected = inputs.get("select")
        if selected is None:
            return payload
        if not isinstance(selected, list):
            return {}
        return {
            key: payload[key]
            for key in selected
            if isinstance(key, str) and key in payload
        }
