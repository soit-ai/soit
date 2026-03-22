""" verifier

Agent verifier.
"""

from dataclasses import dataclass
from typing import List, Optional
import json

from app.kernel.ports.llm.interface import LLMPort, ChatMessage


@dataclass
class VerifierResult:
    """Verifier result payload."""

    ok: bool
    reason: Optional[str]
    tokens_prompt: int
    tokens_completion: int
    finish_reason: Optional[str]


class AgentVerifier:
    """Verify agent response."""

    def __init__(self, llm_port: Optional[LLMPort] = None):
        self.llm_port = llm_port

    async def verify(
        self,
        messages: List[ChatMessage],
        response: str,
        model: str,
        run_id: str,
    ) -> VerifierResult:
        """Verify response."""
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
            content="You are a verifier. Reply with JSON {'ok': true|false, 'reason': '...'}",
        )
        review = ChatMessage(
            role="user",
            content=f"Response to verify:\n{response}",
        )
        result = await self.llm_port.chat(
            messages=[system, review],
            model=model,
            temperature=0,
            run_id=run_id,
        )
        text = result.text or ""
        ok = "\"ok\": true" in text or "\"ok\":true" in text
        reason = None

        try:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                payload = json.loads(text[start:end + 1])
            else:
                payload = json.loads(text)
            ok = bool(payload.get("ok"))
            reason = payload.get("reason")
        except Exception:
            reason = None

        return VerifierResult(
            ok=ok,
            reason=reason,
            tokens_prompt=result.tokens_prompt,
            tokens_completion=result.tokens_completion,
            finish_reason=result.finish_reason,
        )
