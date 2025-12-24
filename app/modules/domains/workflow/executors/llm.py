""" llm

LLM node executor.
"""

from typing import Dict, Any, List
from app.modules.domains.workflow.executors.base import NodeExecutor, ExecutionContext
from app.kernel.gateways.llm.interface import ChatMessage, ChatResponse
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
        if not context.llm_gateway:
            raise ValidationError("LLM gateway not available")
        
        # Extract parameters
        prompt = inputs.get("prompt") or inputs.get("message")
        if not prompt:
            raise ValidationError("LLM node requires 'prompt' or 'message' input")
        
        model = inputs.get("model", "model:openai:gpt-3.5-turbo")
        temperature = inputs.get("temperature")
        max_tokens = inputs.get("max_tokens")
        
        # Build messages
        messages = []
        if inputs.get("system"):
            messages.append(ChatMessage(role="system", content=inputs["system"]))
        messages.append(ChatMessage(role="user", content=str(prompt)))
        
        # Call LLM gateway
        response: ChatResponse = await context.llm_gateway.chat(
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

