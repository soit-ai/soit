""" planner

Agent planner using native LLM function calling.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from app.kernel.ports.llm.interface import LLMPort, ChatMessage, ToolDefinition, ToolCall


@dataclass
class PlanResult:
    """Planner result payload."""

    action: str  # "tool" or "respond"
    tool_calls: Optional[List[ToolCall]]
    response: Optional[str]
    raw: Dict[str, Any]
    tokens_prompt: int
    tokens_completion: int
    finish_reason: Optional[str]

    # TODO(task-7): remove these compat properties after service.py rewrite
    @property
    def tool_ref(self) -> Optional[str]:
        """Backward compat: first tool call name."""
        if self.tool_calls:
            return self.tool_calls[0].name
        return None

    @property
    def parameters(self) -> Dict[str, Any]:
        """Backward compat: first tool call arguments."""
        if self.tool_calls:
            return self.tool_calls[0].arguments
        return {}


class AgentPlanner:
    """LLM-based planner for agent steps using native function calling."""

    def __init__(self, llm_port: LLMPort):
        self.llm_port = llm_port

    async def plan(
        self,
        messages: List[ChatMessage],
        tool_definitions: Optional[List[ToolDefinition]],
        model: str,
        temperature: Optional[float],
        run_id: str,
        memory_context: Optional[str] = None,
        rag_context: Optional[str] = None,
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
            )

        return PlanResult(
            action="respond",
            tool_calls=None,
            response=response.text or "",
            raw={},
            tokens_prompt=response.tokens_prompt,
            tokens_completion=response.tokens_completion,
            finish_reason=response.finish_reason,
        )
