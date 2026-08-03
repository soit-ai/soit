"""LLM-as-judge scoring for regression cases."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.kernel.ports.llm.interface import ChatMessage, LLMPort

DEFAULT_JUDGE_TEMPERATURE = 0.0
_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

_SYSTEM_PROMPT = (
    "You are a strict evaluation judge. Score how well a model output satisfies "
    "a rubric, given the original input. Respond with a single JSON object and "
    'nothing else: {"score": <float between 0 and 1>, "reasoning": "<short '
    'justification>"}. A score of 1 means the rubric is fully satisfied.'
)


@dataclass(frozen=True)
class JudgeVerdict:
    """Score produced by a judge for one case output."""

    score: float
    reasoning: str
    model: str | None = None


class JudgeError(Exception):
    """The judge could not produce a usable verdict."""


class RegressionJudge(Protocol):
    """Scores a case output against a rubric."""

    async def score(
        self,
        *,
        rubric: str,
        case_input: dict[str, Any],
        output: str,
        model: str | None = None,
    ) -> JudgeVerdict: ...


class LLMRegressionJudge:
    """Judge backed by the governed LLM port.

    Calls flow through the same policy gateway as every other model call, so
    judge usage is subject to egress policy and shows up in cost attribution.
    """

    def __init__(self, *, llm_port: LLMPort, default_model: str) -> None:
        self._llm_port = llm_port
        self._default_model = default_model

    async def score(
        self,
        *,
        rubric: str,
        case_input: dict[str, Any],
        output: str,
        model: str | None = None,
    ) -> JudgeVerdict:
        judge_model = model or self._default_model
        try:
            response = await self._llm_port.chat(
                [
                    ChatMessage(role="system", content=_SYSTEM_PROMPT),
                    ChatMessage(
                        role="user",
                        content=(
                            f"Rubric:\n{rubric}\n\n"
                            f"Original input:\n{json.dumps(case_input, ensure_ascii=False)}\n\n"
                            f"Output under evaluation:\n{output}"
                        ),
                    ),
                ],
                model=judge_model,
                temperature=DEFAULT_JUDGE_TEMPERATURE,
            )
        except Exception as exc:
            # The report must record the judge as failed, not crash: a flaky
            # judge model would otherwise abort every case after it.
            raise JudgeError(f"judge model call failed: {exc}") from exc
        return _parse_verdict(response.text, model=response.model or judge_model)


def _parse_verdict(text: str | None, *, model: str | None) -> JudgeVerdict:
    if not text:
        raise JudgeError("judge returned an empty response")
    match = _JSON_OBJECT_PATTERN.search(text)
    if match is None:
        raise JudgeError("judge response contains no JSON object")
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise JudgeError(f"judge response is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict) or "score" not in payload:
        raise JudgeError("judge response is missing a score")
    try:
        score = float(payload["score"])
    except (TypeError, ValueError) as exc:
        raise JudgeError("judge score is not a number") from exc
    return JudgeVerdict(
        score=min(1.0, max(0.0, score)),
        reasoning=str(payload.get("reasoning") or ""),
        model=model,
    )
