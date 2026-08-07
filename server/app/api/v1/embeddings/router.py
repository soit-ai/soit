"""Routes for governed text embeddings.

Thin northbound wrapper over the LLM gateway's ``embed``: it creates one Run
per request so cost entries (``billing_basis="embeddings"``) attach to a run
that external billing consumers can pull, then returns the vectors inline.
Vector storage stays with the caller by design — the platform does not persist
embeddings (callers that want managed retrieval use the knowledge module
instead).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.v1.permissions import require_workspace_write_ctx
from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.runs.writer import TraceWriter
from app.wiring import get_container

router = APIRouter()

MAX_INPUT_ITEMS = 256
MAX_ITEM_CHARS = 8192


class EmbeddingCreate(BaseModel):
    """Embedding request (OpenAI-compatible shape, reduced)."""

    model: str = Field(min_length=1)
    input: str | list[str] = Field()

    @field_validator("input")
    @classmethod
    def _bounded_input(cls, value: str | list[str]) -> str | list[str]:
        """Reject oversized batches before the request is billed."""
        items = [value] if isinstance(value, str) else value
        if len(items) == 0:
            raise ValueError("input must not be empty")
        if len(items) > MAX_INPUT_ITEMS:
            raise ValueError(f"input must contain at most {MAX_INPUT_ITEMS} items")
        for item in items:
            if not item.strip():
                raise ValueError("input items must not be blank")
            if len(item) > MAX_ITEM_CHARS:
                raise ValueError(f"input items must be at most {MAX_ITEM_CHARS} characters")
        return value


class EmbeddingRead(BaseModel):
    run_id: str
    model: str | None
    embeddings: list[list[float]]
    tokens_used: int


@router.post(
    "",
    response_model=EmbeddingRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_embeddings(
    payload: EmbeddingCreate,
    ctx: Annotated[RequestContext, Depends(require_workspace_write_ctx)],
    db: Annotated[Session, Depends(get_db)],
) -> EmbeddingRead:
    """Embed texts and record usage against a dedicated run."""

    texts = [payload.input] if isinstance(payload.input, str) else payload.input

    container = get_container()
    trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
    llm_port = container.get_llm_port(ctx=ctx, trace_writer=trace_writer)

    run = trace_writer.create_run(
        "embedding",
        input_summary=f"model={payload.model}, texts={len(texts)}",
    )
    trace_writer.update_run_status(run.id, "running")
    db.commit()
    try:
        response = await llm_port.embed(
            texts=texts,
            model=payload.model,
            run_id=run.id,
        )
        trace_writer.update_run_status(
            run.id,
            "succeeded",
            output_summary=f"embeddings={len(response.embeddings)}",
        )
        db.commit()
    except Exception as exc:
        trace_writer.update_run_status(
            run.id,
            "failed",
            error_code="EMBED_ERROR",
            error_message=str(exc)[:2000],
        )
        db.commit()
        raise

    return EmbeddingRead(
        run_id=run.id,
        model=response.model,
        embeddings=response.embeddings,
        tokens_used=response.tokens_used,
    )
