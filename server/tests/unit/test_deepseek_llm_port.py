"""Unit tests for DeepSeekLLMPort model parsing."""

from app.adapters.llm.deepseek import DeepSeekLLMPort


def test_deepseek_model_ref_parsing_preserves_colon_suffix() -> None:
    assert DeepSeekLLMPort._resolve_model_name("model:deepseek:deepseek-r1:8b") == "deepseek-r1:8b"
    assert DeepSeekLLMPort._resolve_model_name("deepseek:deepseek-chat") == "deepseek-chat"
    assert DeepSeekLLMPort._resolve_model_name("deepseek-r1:8b") == "deepseek-r1:8b"
