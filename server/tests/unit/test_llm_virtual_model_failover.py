"""A virtual model moves to its next target when a provider is in trouble."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.kernel.commons.errors import KernelError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingResponse,
    GeneratedImage,
    ImageGenerationResponse,
    LLMRuntimeTarget,
)
from app.kernel.ports.llm.policy import LLMPolicyGateway

CTX = RequestContext(tenant_id="t", workspace_id="w", user_id="u", workspace_role="Dev")
MESSAGES = [ChatMessage(role="user", content="hello")]
PRIMARY = "model:primary:big"
BACKUP = "model:backup:small"


class _ProviderError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"provider answered {status_code}")
        self.status_code = status_code


class _Port:
    """One provider: answers, or fails with a status, before or after streaming."""

    def __init__(self, name: str, *, fail: int | None = None, fail_mid_stream: bool = False) -> None:
        self.name = name
        self.fail = fail
        self.fail_mid_stream = fail_mid_stream
        self.calls: list[str] = []

    def _check(self, model: str) -> None:
        self.calls.append(model)
        if self.fail is not None:
            raise _ProviderError(self.fail)

    async def chat(self, *, model: str, **kwargs: Any) -> ChatResponse:
        self._check(model)
        return ChatResponse(text=self.name, tokens_prompt=3, tokens_completion=2, model=self.name)

    async def stream_chat(self, *, model: str, **kwargs: Any) -> AsyncIterator[ChatStreamChunk]:
        self._check(model)
        yield ChatStreamChunk(delta=f"{self.name}.\n", model=self.name)
        if self.fail_mid_stream:
            raise _ProviderError(503)
        yield ChatStreamChunk(done=True, finish_reason="stop", tokens_prompt=3, tokens_completion=2)

    async def embed(self, *, model: str, **kwargs: Any) -> EmbeddingResponse:
        self._check(model)
        return EmbeddingResponse(embeddings=[[1.0]], tokens_used=2, model=self.name)

    async def generate_image(self, *, model: str, **kwargs: Any) -> ImageGenerationResponse:
        self._check(model)
        return ImageGenerationResponse(images=[GeneratedImage(b64_json="aGk=")], model=self.name)


class _Route:
    def __init__(self, port: _Port, model: str) -> None:
        provider = model.split(":")[1]
        self.port = port
        self.target = LLMRuntimeTarget(
            provider_id=f"prov_{provider}",
            provider_slug=provider,
            provider_kind="openai",
            adapter_backend="native",
            model_ref=model,
            model_id=model.split(":")[2],
        )
        self.timeout_seconds = 5.0
        self.max_retries = 0
        self.retry_backoff = "none"
        self.retryable_status_codes = (408, 409, 429, 500, 502, 503, 504)
        self.pricing: dict[str, Any] = {}
        self.image_capabilities: dict[str, Any] = {}


class _Router:
    """Resolves concrete refs to ports; a missing entry is a disabled model."""

    def __init__(self, ports: dict[str, _Port]) -> None:
        self.ports = ports

    async def resolve_route(self, model: str, ctx: Any, required_capabilities: tuple[str, ...]) -> _Route:
        port = self.ports.get(model)
        if port is None:
            raise KernelError("MODEL_RUNTIME_DISABLED", f"Workspace model is disabled: {model}")
        return _Route(port, model)

    def stream_chat(self, **kwargs: Any) -> Any:  # pragma: no cover - routed per target
        raise AssertionError("calls go through the resolved route")


class _VirtualModels:
    def __init__(self, targets: dict[str, list[str]]) -> None:
        self.targets = targets

    async def resolve_targets(self, ctx: RequestContext, slug: str) -> list[str] | None:
        return self.targets.get(slug)


def _writer() -> MagicMock:
    writer = MagicMock()
    step = MagicMock()
    step.id = "step_1"
    writer.create_step = AsyncMock(return_value=step)
    writer.update_step_status = AsyncMock()
    writer.record_cost = AsyncMock()
    writer.release_before_wait = AsyncMock()
    return writer


def _gateway(ports: dict[str, _Port], writer: MagicMock | None = None) -> LLMPolicyGateway:
    return LLMPolicyGateway(
        gateway=_Router(ports),  # type: ignore[arg-type]
        ctx=CTX,
        trace_writer=writer,
        retry_backoff_base_seconds=0,
        virtual_models=_VirtualModels({"fast": [PRIMARY, BACKUP]}),
    )


def _step_metrics(writer: MagicMock) -> dict[str, Any]:
    return writer.update_step_status.await_args.kwargs["metrics"]


@pytest.mark.asyncio
async def test_a_server_error_moves_the_call_to_the_next_target() -> None:
    primary, backup = _Port("primary", fail=503), _Port("backup")
    writer = _writer()

    response = await _gateway({PRIMARY: primary, BACKUP: backup}, writer).chat(
        MESSAGES, "vmodel:fast", run_id="run_1"
    )

    assert response.text == "backup"
    assert (primary.calls, backup.calls) == ([PRIMARY], [BACKUP])
    assert _step_metrics(writer)["attempts"] == [
        {"model_ref": PRIMARY, "outcome": "failed", "reason": "status_503"},
        {"model_ref": BACKUP, "outcome": "succeeded"},
    ]
    cost = writer.record_cost.await_args.kwargs
    assert cost["model_ref"] == BACKUP
    assert cost["provider_slug"] == "backup"


@pytest.mark.asyncio
async def test_an_invalid_request_is_not_repeated_on_another_provider() -> None:
    primary, backup = _Port("primary", fail=400), _Port("backup")

    with pytest.raises(_ProviderError):
        await _gateway({PRIMARY: primary, BACKUP: backup}).chat(MESSAGES, "vmodel:fast")

    assert backup.calls == []


@pytest.mark.asyncio
async def test_an_unavailable_target_is_skipped() -> None:
    backup = _Port("backup")
    writer = _writer()

    response = await _gateway({BACKUP: backup}, writer).embed(["x"], "vmodel:fast", run_id="run_1")

    assert response.model == "backup"
    assert _step_metrics(writer)["attempts"][0] == {
        "model_ref": PRIMARY,
        "outcome": "unavailable",
        "reason": "MODEL_RUNTIME_DISABLED",
    }


@pytest.mark.asyncio
async def test_when_every_target_fails_the_last_error_is_raised() -> None:
    ports = {PRIMARY: _Port("primary", fail=503), BACKUP: _Port("backup", fail=429)}

    with pytest.raises(_ProviderError) as raised:
        await _gateway(ports).chat(MESSAGES, "vmodel:fast")

    assert raised.value.status_code == 429


@pytest.mark.asyncio
async def test_a_stream_moves_on_only_before_its_first_chunk() -> None:
    primary, backup = _Port("primary", fail=502), _Port("backup")
    gateway = _gateway({PRIMARY: primary, BACKUP: backup})

    text = "".join([chunk.delta async for chunk in gateway.stream_chat(MESSAGES, "vmodel:fast")])

    assert text == "backup.\n"

    broken = _Port("primary", fail_mid_stream=True)
    spare = _Port("backup")
    gateway = _gateway({PRIMARY: broken, BACKUP: spare})
    received: list[str] = []
    with pytest.raises(_ProviderError):
        async for chunk in gateway.stream_chat(MESSAGES, "vmodel:fast"):
            received.append(chunk.delta)
    # Output already reached the consumer, so the stream is not restarted elsewhere.
    assert received == ["primary.\n"]
    assert spare.calls == []


@pytest.mark.asyncio
async def test_images_take_the_first_available_target_and_never_repeat_a_call() -> None:
    primary, backup = _Port("primary", fail=503), _Port("backup")

    with pytest.raises(_ProviderError):
        await _gateway({PRIMARY: primary, BACKUP: backup}).generate_image("a cat", "vmodel:fast")
    assert backup.calls == []

    image = await _gateway({BACKUP: backup}).generate_image("a cat", "vmodel:fast")
    assert image.model == "backup"


@pytest.mark.asyncio
async def test_an_unknown_virtual_model_is_not_found() -> None:
    with pytest.raises(KernelError) as missing:
        await _gateway({}).chat(MESSAGES, "vmodel:nope")

    assert missing.value.code == "MODEL_RUNTIME_NOT_FOUND"


@pytest.mark.asyncio
async def test_a_concrete_model_records_no_attempts() -> None:
    writer = _writer()

    await _gateway({PRIMARY: _Port("primary")}, writer).chat(MESSAGES, PRIMARY, run_id="run_1")

    assert "attempts" not in _step_metrics(writer)
