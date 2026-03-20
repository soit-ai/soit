""" llm

LLM node executor.
"""

from typing import Dict, Any, List
from app.kernel.commons.time import utc_now
from app.modules.workflow.runtime.executors.base import NodeExecutor, ExecutionContext
from app.kernel.ports.llm.interface import ChatMessage, ChatResponse
from app.kernel.commons.errors import ValidationError


class LLMNodeExecutor(NodeExecutor):
    """Executor for LLM nodes."""

    def _response_output_payload(self, response: ChatResponse, model: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "text": response.text,
            "model": response.model or model,
        }
        if response.finish_reason:
            payload["finish_reason"] = response.finish_reason
        return payload

    def _response_usage_payload(self, response: ChatResponse) -> Dict[str, Any]:
        prompt_tokens = int(response.tokens_prompt or 0)
        completion_tokens = int(response.tokens_completion or 0)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
    
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
        
        linked_response = None
        if context.response_service:
            linked_response = context.response_service.create_linked_response(
                run_id=context.run_id,
                model=model,
                input_json={
                    "messages": [{"role": message.role, "content": message.content} for message in messages],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "node_id": node.get("id"),
                    "node_type": node.get("type"),
                    "source": "workflow.llm_node",
                },
                metadata_json={
                    "source": "workflow.llm_node",
                    "step_id": context.step_id,
                    "node_id": node.get("id"),
                    "node_type": node.get("type"),
                },
            )
            linked_response.status = "in_progress"
            linked_response = context.response_service.save_response(linked_response)

        try:
            response: ChatResponse = await context.llm_port.chat(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                run_id=context.run_id,
            )
        except Exception as exc:
            if linked_response:
                linked_response.status = "failed"
                linked_response.error_code = "workflow_llm_failed"
                linked_response.error_message = str(exc)
                linked_response = context.response_service.save_response(linked_response)
                context.response_service.append_event(
                    response=linked_response,
                    event_type="response.failed",
                    payload={
                        "response_id": linked_response.id,
                        "run_id": linked_response.run_id,
                        "step_id": context.step_id,
                        "node_id": node.get("id"),
                        "status": linked_response.status,
                        "error": {"code": linked_response.error_code, "message": linked_response.error_message},
                    },
                    source="workflow",
                )
            raise

        if linked_response:
            linked_response.output_json = self._response_output_payload(response, model)
            linked_response.usage_json = self._response_usage_payload(response)
            linked_response.status = "completed"
            linked_response.completed_at = utc_now()
            linked_response.error_code = None
            linked_response.error_message = None
            linked_response = context.response_service.save_response(linked_response)
            context.response_service.append_event(
                response=linked_response,
                event_type="response.output_text.completed",
                payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "step_id": context.step_id,
                    "node_id": node.get("id"),
                    "output": linked_response.output_json,
                    "usage": linked_response.usage_json,
                },
                source="workflow",
            )
            context.response_service.append_event(
                response=linked_response,
                event_type="response.completed",
                payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "step_id": context.step_id,
                    "node_id": node.get("id"),
                    "status": linked_response.status,
                    "usage": linked_response.usage_json,
                },
                source="workflow",
            )
        
        # Return output
        output = {
            "text": response.text,
            "model": response.model or model,
        }
        if linked_response:
            output["response_id"] = linked_response.id
        
        if response.finish_reason:
            output["finish_reason"] = response.finish_reason
        
        return output
