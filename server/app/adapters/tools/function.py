""" function_tools

Local function tool adapter implementation.
"""

import importlib
import inspect
from typing import Any

from app.kernel.ports.tools.interface import ToolPort, ToolResponse


class FunctionToolsPort(ToolPort):
    """Execute local python functions as tools."""

    async def invoke(
        self,
        tool_ref: str,
        parameters: dict[str, Any],
        **kwargs: Any,
    ) -> ToolResponse:
        """Invoke a function tool."""
        entrypoint = parameters.get("entrypoint")
        inputs = parameters.get("inputs") or {}
        if not entrypoint or ":" not in entrypoint:
            return ToolResponse(result=None, success=False, error="Missing function entrypoint")

        module_path, func_name = entrypoint.split(":", 1)
        try:
            module = importlib.import_module(module_path)
            func = getattr(module, func_name)
        except Exception as exc:
            return ToolResponse(result=None, success=False, error=str(exc))

        try:
            if inspect.iscoroutinefunction(func):
                result = await func(**inputs) if isinstance(inputs, dict) else await func(inputs)
            else:
                result = func(**inputs) if isinstance(inputs, dict) else func(inputs)
            return ToolResponse(result=result, success=True)
        except Exception as exc:
            return ToolResponse(result=None, success=False, error=str(exc))
