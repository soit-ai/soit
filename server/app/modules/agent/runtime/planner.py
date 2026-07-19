""" planner

Agent planner using native LLM function calling.
"""

from dataclasses import dataclass
from typing import Any

from app.kernel.ports.llm.interface import (
    ChatMessage,
    LLMPort,
    ToolCall,
    ToolDefinition,
)


@dataclass
class PlanResult:
    """Planner result payload."""

    action: str  # "tool" or "respond"
    tool_calls: list[ToolCall] | None
    response: str | None
    raw: dict[str, Any]
    tokens_prompt: int
    tokens_completion: int
    finish_reason: str | None
    reasoning: str | None = None


class AgentPlanner:
    """LLM-based planner for agent steps using native function calling."""

    def __init__(self, llm_port: LLMPort):
        self.llm_port = llm_port

    async def plan(
        self,
        messages: list[ChatMessage],
        tool_definitions: list[ToolDefinition] | None,
        model: str,
        temperature: float | None,
        run_id: str,
        memory_context: str | None = None,
        rag_context: str | None = None,
        reasoning_effort: str | None = None,
    ) -> PlanResult:
        """Plan next action using native function calling."""
        planning_messages = list(messages)
        if rag_context:
            planning_messages.insert(
                0,
                ChatMessage(
                    role="system",
                    content=f"Retrieved knowledge context:\n{rag_context}",
                ),
            )
        if memory_context:
            planning_messages.insert(
                0,
                ChatMessage(
                    role="system",
                    content=f"Relevant memory context:\n{memory_context}",
                ),
            )

        response = await self.llm_port.chat(
            messages=planning_messages,
            model=model,
            temperature=temperature,
            tools=tool_definitions if tool_definitions else None,
            tool_choice="auto" if tool_definitions else None,
            run_id=run_id,
            reasoning_effort=reasoning_effort,
        )

        if response.tool_calls:
            return PlanResult(
                action="tool",
                tool_calls=response.tool_calls,
                response=None,
                raw={},
                tokens_prompt=response.tokens_prompt,
                tokens_completion=response.tokens_completion,
                finish_reason=response.finish_reason,
                reasoning=response.reasoning,
            )

        return PlanResult(
            action="respond",
            tool_calls=None,
            response=response.text or "",
            raw={},
            tokens_prompt=response.tokens_prompt,
            tokens_completion=response.tokens_completion,
            finish_reason=response.finish_reason,
            reasoning=response.reasoning,
        )
