"""Unit tests for LLM-as-judge scoring."""

from __future__ import annotations

from typing import Any

import pytest

from app.kernel.ports.llm.interface import ChatResponse
from app.modules.evaluation.application.judge import (
    JudgeError,
    LLMRegressionJudge,
    _parse_verdict,
)


class _StubLLMPort:
    def __init__(self, *, text: str | None = None, error: Exception | None = None):
        self.text = text
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        self.calls.append({"messages": messages, "model": model})
        if self.error is not None:
            raise self.error
        return ChatResponse(text=self.text, model=model)


@pytest.mark.asyncio
async def test_judge_parses_scores_and_uses_case_specific_model_override() -> None:
    port = _StubLLMPort(text='{"score": 0.9, "reasoning": "matches rubric"}')
    judge = LLMRegressionJudge(llm_port=port, default_model="model:openai:gpt-4o-mini")

    verdict = await judge.score(
        rubric="Answer must cite the refund policy.",
        case_input={"messages": [{"role": "user", "content": "refund?"}]},
        output="Per the refund policy, verification is required.",
        model="model:anthropic:claude-sonnet-5",
    )

    assert verdict.score == 0.9
    assert verdict.reasoning == "matches rubric"
    assert port.calls[0]["model"] == "model:anthropic:claude-sonnet-5"


@pytest.mark.asyncio
async def test_judge_falls_back_to_default_model() -> None:
    port = _StubLLMPort(text='{"score": 1, "reasoning": "ok"}')
    judge = LLMRegressionJudge(llm_port=port, default_model="model:openai:gpt-4o-mini")

    await judge.score(rubric="rubric", case_input={}, output="output")

    assert port.calls[0]["model"] == "model:openai:gpt-4o-mini"


@pytest.mark.asyncio
async def test_judge_wraps_model_call_failures_as_judge_errors() -> None:
    port = _StubLLMPort(error=RuntimeError("provider unavailable"))
    judge = LLMRegressionJudge(llm_port=port, default_model="model:openai:gpt-4o-mini")

    with pytest.raises(JudgeError, match="judge model call failed"):
        await judge.score(rubric="rubric", case_input={}, output="output")


def test_parse_verdict_extracts_json_from_surrounding_prose_and_clamps() -> None:
    verdict = _parse_verdict(
        'Here is my assessment: {"score": 1.7, "reasoning": "beyond scale"} done.',
        model="m",
    )
    assert verdict.score == 1.0
    assert verdict.reasoning == "beyond scale"


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "no json here",
        '{"reasoning": "missing score"}',
        '{"score": "not-a-number"}',
    ],
)
def test_parse_verdict_rejects_unusable_responses(text: str | None) -> None:
    with pytest.raises(JudgeError):
        _parse_verdict(text, model="m")
