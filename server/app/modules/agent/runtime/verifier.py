""" verifier

Agent verifier using structured output via function calling.
"""

from dataclasses import dataclass

from app.kernel.ports.llm.interface import ChatMessage, LLMPort, ToolDefinition

VERIFY_TOOL = ToolDefinition(
    name="verify_response",
    description="Verify whether the agent response adequately addresses the user query.",
    parameters={
        "type": "object",
        "properties": {
            "ok": {"type": "boolean", "description": "Whether the response is adequate"},
            "reason": {"type": "string", "description": "Brief explanation"},
        },
        "required": ["ok"],
    },
)


@dataclass
class VerifierResult:
    """Verifier result payload."""

    ok: bool
    reason: str | None
    tokens_prompt: int
    tokens_completion: int
    finish_reason: str | None


class AgentVerifier:
    """Verify agent response using structured output."""

    def __init__(self, llm_port: LLMPort | None = None):
        self.llm_port = llm_port

    async def verify(
        self,
        messages: list[ChatMessage],
        response: str,
        model: str,
        run_id: str,
    ) -> VerifierResult:
        """Verify response quality."""
        if not self.llm_port:
            return VerifierResult(
                ok=True,
                reason=None,
                tokens_prompt=0,
                tokens_completion=0,
                finish_reason=None,
            )

        system = ChatMessage(
            role="system",
            content="You are a response quality verifier. Use the verify_response tool to report your assessment.",
        )
        review = ChatMessage(
            role="user",
            content=f"Response to verify:\n{response}",
        )
        result = await self.llm_port.chat(
            messages=[system, review],
            model=model,
            temperature=0,
            tools=[VERIFY_TOOL],
            tool_choice="required",
            run_id=run_id,
        )

        # Extract structured result from tool call
        ok = True
        reason = None
        if result.tool_calls:
            args = result.tool_calls[0].arguments
            ok = bool(args.get("ok", True))
            reason = args.get("reason")

        return VerifierResult(
            ok=ok,
            reason=reason,
            tokens_prompt=result.tokens_prompt,
            tokens_completion=result.tokens_completion,
            finish_reason=result.finish_reason,
        )
