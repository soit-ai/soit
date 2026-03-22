""" planner

Agent planner.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json

from app.kernel.ports.llm.interface import LLMPort, ChatMessage


@dataclass
class PlanResult:
    """Planner result payload."""

    action: str
    tool_ref: Optional[str]
    parameters: Dict[str, Any]
    response: Optional[str]
    raw: Dict[str, Any]
    tokens_prompt: int
    tokens_completion: int
    finish_reason: Optional[str]


class AgentPlanner:
    """LLM-based planner for agent steps."""

    def __init__(self, llm_port: LLMPort):
        self.llm_port = llm_port

    async def plan(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[str]],
        memory_context: Optional[str],
        model: str,
        temperature: Optional[float],
        run_id: str,
    ) -> PlanResult:
        """Plan next action."""
        system_lines = [
            "You are an agent planner.",
            "Return a single JSON object with fields:",
            "action: 'tool' or 'respond'",
            "tool_ref: required if action is 'tool'",
            "parameters: tool parameters when action is 'tool'",
            "response: final response when action is 'respond'",
        ]
        if tools:
            system_lines.append(f"Allowed tools: {', '.join(tools)}")
        if memory_context:
            system_lines.append(f"Memory context:\n{memory_context}")

        system = ChatMessage(role="system", content="\n".join(system_lines))
        planning_messages = [system] + messages

        response = await self.llm_port.chat(
            messages=planning_messages,
            model=model,
            temperature=temperature,
            run_id=run_id,
        )

        text = response.text or ""
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                payload = json.loads(text[start:end + 1])
            else:
                payload = json.loads(text)
        except Exception:
            payload = {"action": "respond", "response": text}

        action = payload.get("action") or "respond"
        tool_ref = payload.get("tool_ref")
        parameters = payload.get("parameters") or {}
        if not isinstance(parameters, dict):
            parameters = {"value": parameters}
        response_text = payload.get("response")

        return PlanResult(
            action=action,
            tool_ref=tool_ref,
            parameters=parameters,
            response=response_text,
            raw=payload,
            tokens_prompt=response.tokens_prompt,
            tokens_completion=response.tokens_completion,
            finish_reason=response.finish_reason,
        )
