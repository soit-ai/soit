""" llm

LLM node executor.
"""

from typing import Dict, Any, List
from app.modules.workflow.runtime.executors.base import NodeExecutor, ExecutionContext
from app.kernel.ports.llm.interface import ChatMessage, ChatResponse
from app.kernel.commons.errors import ValidationError


class LLMNodeExecutor(NodeExecutor):
    """Executor for LLM nodes."""
    
    async def execute(
        self,
        node: Dict[str, Any],
        context: ExecutionContext,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute LLM node.
        
        Args:
            node: Node definition.
            context: Execution context.
            inputs: Resolved inputs.
            
        Returns:
            Output dictionary with 'text' and optional 'model'.
        """
        if not context.llm_port:
            raise ValidationError("LLM gateway not available")
        
        # Extract parameters
        prompt = inputs.get("prompt") or inputs.get("message")
        messages_input = inputs.get("messages")
        model = inputs.get("model", "model:openai:gpt-5.1")
        temperature = inputs.get("temperature")
        max_tokens = inputs.get("max_tokens")

        # Build messages
        messages = []
        if messages_input is not None:
            if not isinstance(messages_input, list):
                raise ValidationError("LLM node 'messages' must be a list")
            for msg in messages_input:
                if not isinstance(msg, dict):
                    raise ValidationError("LLM node message must be an object")
                role = msg.get("role", "user")
                content = msg.get("content", "")
                messages.append(ChatMessage(role=role, content=str(content)))
        else:
            if not prompt:
                raise ValidationError("LLM node requires 'prompt', 'message', or 'messages' input")
            messages.append(ChatMessage(role="user", content=str(prompt)))

        if inputs.get("system"):
            messages = [ChatMessage(role="system", content=inputs["system"])] + messages

        if not messages:
            raise ValidationError("LLM node requires at least one message")
        
        # Call LLM gateway
        response: ChatResponse = await context.llm_port.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            run_id=context.run_id,
        )
        
        # Return output
        output = {
            "text": response.text,
            "model": response.model or model,
        }
        
        if response.finish_reason:
            output["finish_reason"] = response.finish_reason
        
        return output
