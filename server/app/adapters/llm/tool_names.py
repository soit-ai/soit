"""Provider-safe aliases for SOIT tool names.

SOIT addresses tools by refs such as ``tool:plugin:search``, while OpenAI and
Anthropic accept function names matching ``^[A-Za-z0-9_-]{1,64}$``. A name
that already fits is sent as it is; any other is normalised and suffixed with
a short digest so two refs never collapse onto one alias. Adapters keep the
reverse map to translate the provider's answer back to the SOIT name.
"""

from __future__ import annotations

import hashlib
import re

from app.kernel.ports.llm.interface import ToolDefinition

TOOL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def tool_name_alias(name: str) -> str:
    if TOOL_NAME_PATTERN.fullmatch(name):
        return name
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_-") or "tool"
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:10]
    return f"{normalized[:53]}_{digest}"


def tool_name_maps(
    tools: list[ToolDefinition] | None,
) -> tuple[dict[str, str], dict[str, str]]:
    """``(SOIT name -> alias, alias -> SOIT name)`` for the offered tools."""

    outbound = {tool.name: tool_name_alias(tool.name) for tool in tools or []}
    return outbound, {alias: original for original, alias in outbound.items()}
