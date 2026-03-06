"""Unit tests for BotAppFacadeService."""

import pytest

from app.kernel.trace.writer import TraceWriter
from app.kernel.trace.models import Run
from app.kernel.ports.llm.interface import LLMPort, ChatResponse, EmbeddingResponse, RerankResponse
from app.modules.bot.application.app_facade import BotAppFacadeService
from app.modules.bot.application.schemas import BotCreate, BotVersionCreate, BotExecuteRequest


class StubLLMPort(LLMPort):
    """Stub LLM port for bot tests."""

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        return ChatResponse(text="ok", model=model, tokens_prompt=1, tokens_completion=2)

    async def embed(self, texts, model, **kwargs):
        return EmbeddingResponse(embeddings=[[0.0]], model=model)

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        return RerankResponse(results=[], model=model)


@pytest.mark.asyncio
async def test_bot_execute_creates_run(db, ctx):
    service = BotAppFacadeService(
        db=db,
        ctx=ctx,
        llm_port=StubLLMPort(),
        trace_writer=TraceWriter(db, ctx),
    )

    bot = await service.create_bot(BotCreate(name="demo", description="x"))
    version = await service.create_version(
        bot.id,
        BotVersionCreate(version="1.0.0", system_prompt="hi", model_ref="model:openai:gpt-5.1"),
    )

    result = await service.execute_bot(
        bot.id,
        BotExecuteRequest(messages=[{"role": "user", "content": "hello"}], version_id=version.id),
    )

    run = db.get(Run, result["run_id"])
    assert run is not None
    assert run.mode == "bot"
    assert run.status == "succeeded"
