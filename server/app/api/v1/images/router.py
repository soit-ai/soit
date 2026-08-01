"""Routes for governed image generation.

Thin northbound wrapper over the LLM gateway's ``generate_image``: it creates
one Run per request so cost entries (``billing_basis="images"``) attach to a
run that external billing consumers can pull, then returns the images inline.
Storage stays with the caller by design — the platform does not persist
generated images.
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

MIN_IMAGE_DIMENSION = 64
MAX_IMAGE_DIMENSION = 4096


class ImageGenerationCreate(BaseModel):
    """Image generation request (OpenAI-compatible shape, reduced)."""

    model: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=4000)
    n: int = Field(default=1, ge=1, le=4)
    size: str | None = Field(default=None, pattern=r"^\d{2,4}x\d{2,4}$")
    response_format: str = Field(default="b64_json", pattern="^(b64_json|url)$")

    @field_validator("size")
    @classmethod
    def _supported_dimensions(cls, value: str | None) -> str | None:
        """Reject dimensions no provider serves, before the request is billed."""
        if value is None:
            return value
        width, _, height = value.partition("x")
        for dimension in (int(width), int(height)):
            if not MIN_IMAGE_DIMENSION <= dimension <= MAX_IMAGE_DIMENSION:
                raise ValueError(
                    "Image dimensions must be between "
                    f"{MIN_IMAGE_DIMENSION} and {MAX_IMAGE_DIMENSION} pixels"
                )
        return value


class ImageDatum(BaseModel):
    b64_json: str | None = None
    url: str | None = None


class ImageGenerationRead(BaseModel):
    run_id: str
    model: str | None
    data: list[ImageDatum]


@router.post(
    "/generations",
    response_model=ImageGenerationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_image_generation(
    payload: ImageGenerationCreate,
    ctx: Annotated[RequestContext, Depends(require_workspace_write_ctx)],
    db: Annotated[Session, Depends(get_db)],
) -> ImageGenerationRead:
    """Generate images and record usage against a dedicated run."""

    container = get_container()
    trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
    llm_port = container.get_llm_port(ctx=ctx, trace_writer=trace_writer)

    run = trace_writer.create_run(
        "image",
        input_summary=f"model={payload.model}, n={payload.n}, prompt={payload.prompt[:200]}",
    )
    trace_writer.update_run_status(run.id, "running")
    db.commit()
    try:
        response = await llm_port.generate_image(
            prompt=payload.prompt,
            model=payload.model,
            n=payload.n,
            size=payload.size,
            response_format=payload.response_format,
            run_id=run.id,
        )
        trace_writer.update_run_status(
            run.id,
            "succeeded",
            output_summary=f"images={len(response.images)}",
        )
        db.commit()
    except Exception as exc:
        trace_writer.update_run_status(
            run.id,
            "failed",
            error_code="IMAGE_ERROR",
            error_message=str(exc)[:2000],
        )
        db.commit()
        raise

    return ImageGenerationRead(
        run_id=run.id,
        model=response.model,
        data=[
            ImageDatum(b64_json=image.b64_json, url=image.url)
            for image in response.images
        ],
    )
