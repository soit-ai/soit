"""deepseek_llm

DeepSeek LLM port adapter implementation.
"""


from app.adapters.llm.openai import OpenAILLMPort
from app.settings.settings import settings


class DeepSeekLLMPort(OpenAILLMPort):
    """DeepSeek LLM port adapter via OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        resolved_api_key = api_key or settings.deepseek_api_key
        resolved_base_url = base_url or settings.deepseek_base_url
        super().__init__(api_key=resolved_api_key, base_url=resolved_base_url)

    @staticmethod
    def _resolve_model_name(model: str) -> str:
        """Resolve model refs while preserving DeepSeek model ids containing ':'."""
        if model.startswith("model:"):
            parts = model.split(":")
            if len(parts) >= 3:
                return ":".join(parts[2:])
        if model.startswith("deepseek:"):
            return model.split(":", 1)[1]
        return model
