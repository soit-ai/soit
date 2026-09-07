"""Routes for governed image generation and editing.

Thin northbound wrapper over the LLM gateway's ``generate_image`` and
``edit_image``: each request creates one Run so cost entries
(``billing_basis="images"``) attach to a run external billing consumers can
pull. Inline results keep storage with the caller by design; ``artifact`` and
``async`` requests write into governed run storage instead, because a batch of
large images does not survive a synchronous response.

Editing covers three shapes through one endpoint, because they are one provider
call: inpainting (image + mask), outpainting (a pre-expanded canvas whose new
margin is masked), and reference editing (image, no mask).
"""

import base64
import binascii
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.api.v1.attachments.dependencies import get_attachment_service
from app.api.v1.permissions import require_workspace_write_ctx
from app.infra.db.session import get_db
from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.image_mask import MASK_CONVENTION, assert_mask_matches_image
from app.kernel.runtime.attachments.service import AttachmentService
from app.kernel.runtime.images.service import (
    ImageJobRequest,
    ImageResult,
    execute_image_job,
)
from app.kernel.runtime.runs.writer import TraceWriter
from app.wiring import get_container
from app.wiring.image_job import start_detached_image_job

router = APIRouter()

MIN_IMAGE_DIMENSION = 64
MAX_IMAGE_DIMENSION = 4096
MAX_INLINE_IMAGE_BYTES = AttachmentService.MAX_FILE_SIZE


def _validate_dimensions(value: str | None) -> str | None:
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


class ImageGenerationCreate(BaseModel):
    """Image generation request (OpenAI-compatible shape, reduced)."""

    model_config = ConfigDict(populate_by_name=True)

    model: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=4000)
    n: int = Field(default=1, ge=1, le=4)
    size: str | None = Field(default=None, pattern=r"^\d{2,4}x\d{2,4}$")
    response_format: str = Field(
        default="b64_json", pattern="^(b64_json|url|artifact)$"
    )
    run_async: bool = Field(default=False, alias="async")

    @field_validator("size")
    @classmethod
    def _supported_dimensions(cls, value: str | None) -> str | None:
        return _validate_dimensions(value)


class ImageDatum(BaseModel):
    b64_json: str | None = None
    url: str | None = None
    attachment_id: str | None = None


class ImageGenerationRead(BaseModel):
    run_id: str
    model: str | None
    status: str
    data: list[ImageDatum]


class ImageEditCreate(BaseModel):
    """Image edit request.

    ``image`` and ``mask`` each arrive either as an ``attachment_id`` or as
    inline base64. Attachments are preferred: a 2048px source is several
    megabytes, and inline bytes make the request body carry them twice over.
    """

    model_config = ConfigDict(populate_by_name=True)

    model: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=4000)
    image_attachment_id: str | None = None
    image_b64: str | None = None
    mask_attachment_id: str | None = None
    mask_b64: str | None = None
    n: int = Field(default=1, ge=1, le=4)
    size: str | None = Field(default=None, pattern=r"^\d{2,4}x\d{2,4}$")
    strength: float | None = Field(default=None, ge=0.0, le=1.0)
    seed: int | None = Field(default=None, ge=0)
    negative_prompt: str | None = Field(default=None, max_length=4000)
    background: str | None = Field(default=None, pattern="^(transparent|opaque)$")
    output_format: str = Field(default="png", pattern="^(png|webp)$")
    response_format: str = Field(
        default="b64_json", pattern="^(b64_json|url|artifact)$"
    )
    run_async: bool = Field(default=False, alias="async")

    @field_validator("size")
    @classmethod
    def _supported_dimensions(cls, value: str | None) -> str | None:
        return _validate_dimensions(value)

    @model_validator(mode="after")
    def _exactly_one_source_per_input(self) -> "ImageEditCreate":
        if bool(self.image_attachment_id) == bool(self.image_b64):
            raise ValueError(
                "Provide the source image as exactly one of "
                "image_attachment_id or image_b64"
            )
        if self.mask_attachment_id and self.mask_b64:
            raise ValueError(
                "Provide the mask as at most one of mask_attachment_id or mask_b64"
            )
        return self


class ImageEditRead(BaseModel):
    run_id: str
    model: str | None
    status: str
    mask_convention: str
    data: list[ImageDatum]


def _decode_inline_image(value: str, *, field: str) -> bytes:
    try:
        data = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValidationError(f"{field} is not valid base64") from exc
    if not data:
        raise ValidationError(f"{field} is empty")
    if len(data) > MAX_INLINE_IMAGE_BYTES:
        raise ValidationError(
            f"{field} exceeds the {MAX_INLINE_IMAGE_BYTES // (1024 * 1024)} MiB limit"
        )
    return data


async def _resolve_image_input(
    service: AttachmentService,
    *,
    attachment_id: str | None,
    inline_b64: str | None,
    field: str,
) -> bytes | None:
    if attachment_id:
        attachment, data = await service.get_content(attachment_id)
        if not attachment.content_type.startswith("image/"):
            raise ValidationError(
                f"{field} attachment is not an image: {attachment.content_type}"
            )
        return data
    if inline_b64:
        return _decode_inline_image(inline_b64, field=field)
    return None


def _output_summary(outcome) -> str:
    """Say what came back and whether anything was flagged.

    The safety count belongs on the run rather than only in the response: the
    response is gone once the caller has it, the run is the durable record.
    """
    summary = f"images={len(outcome.results)}"
    if outcome.safety:
        summary = f"{summary}, safety_findings={len(outcome.safety)}"
    return summary


def _to_data(results: list[ImageResult]) -> list[ImageDatum]:
    return [
        ImageDatum(
            b64_json=result.b64_json,
            url=result.url,
            attachment_id=result.attachment_id,
        )
        for result in results
    ]


async def _submit(
    request: ImageJobRequest,
    *,
    ctx: RequestContext,
    db: Session,
    run_async: bool,
    response: Response,
) -> tuple[str, str, str | None, list[ImageDatum]]:
    """Open a run and either finish the job now or hand it to a worker.

    Returns the run id, its status, the model, and whatever results exist yet.
    """
    container = get_container()
    trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())

    run = trace_writer.create_run("image", input_summary=request.summary)

    if run_async:
        # The run is committed while still queued so the caller can poll it the
        # moment this responds; the worker owns every transition after this.
        db.commit()
        start_detached_image_job(
            bind=db.get_bind(),
            ctx=ctx,
            request=request,
            run_id=run.id,
        )
        response.status_code = status.HTTP_202_ACCEPTED
        return run.id, "queued", None, []

    trace_writer.update_run_status(run.id, "running")
    db.commit()
    try:
        outcome = await execute_image_job(
            request,
            run_id=run.id,
            ctx=ctx,
            llm_port=container.get_llm_port(ctx=ctx, trace_writer=trace_writer),
            trace_writer=trace_writer,
            storage_port=container.get_storage_port(ctx=ctx),
            content_safety=container.get_content_safety_port(ctx),
        )
        trace_writer.update_run_status(
            run.id,
            "succeeded",
            output_summary=_output_summary(outcome),
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

    return run.id, "succeeded", outcome.model, _to_data(outcome.results)


@router.post(
    "/generations",
    response_model=ImageGenerationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_image_generation(
    payload: ImageGenerationCreate,
    ctx: Annotated[RequestContext, Depends(require_workspace_write_ctx)],
    db: Annotated[Session, Depends(get_db)],
    response: Response,
) -> ImageGenerationRead:
    """Generate images and record usage against a dedicated run."""

    run_id, run_status, model, data = await _submit(
        ImageJobRequest(
            kind="generate",
            model=payload.model,
            prompt=payload.prompt,
            n=payload.n,
            size=payload.size,
            response_format=payload.response_format,
        ),
        ctx=ctx,
        db=db,
        run_async=payload.run_async,
        response=response,
    )
    return ImageGenerationRead(
        run_id=run_id, model=model, status=run_status, data=data
    )


@router.post(
    "/edits",
    response_model=ImageEditRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_image_edit(
    payload: ImageEditCreate,
    ctx: Annotated[RequestContext, Depends(require_workspace_write_ctx)],
    db: Annotated[Session, Depends(get_db)],
    attachments: Annotated[AttachmentService, Depends(get_attachment_service)],
    response: Response,
) -> ImageEditRead:
    """Edit an image and record usage against a dedicated run.

    The mask convention is fixed here rather than left to the provider: white
    marks the region to edit. Adapters convert to whatever their provider reads,
    so the same mask means the same thing on every route.
    """

    image = await _resolve_image_input(
        attachments,
        attachment_id=payload.image_attachment_id,
        inline_b64=payload.image_b64,
        field="image",
    )
    mask = await _resolve_image_input(
        attachments,
        attachment_id=payload.mask_attachment_id,
        inline_b64=payload.mask_b64,
        field="mask",
    )
    if mask is not None:
        # A silently resized mask shifts the selection, which reads as the
        # model ignoring the selection rather than as a bad request.
        assert_mask_matches_image(image, mask)

    extra: dict[str, Any] = {}
    for name in ("strength", "seed", "negative_prompt", "background"):
        value = getattr(payload, name)
        if value is not None:
            extra[name] = value

    run_id, run_status, model, data = await _submit(
        ImageJobRequest(
            kind="edit",
            model=payload.model,
            prompt=payload.prompt,
            n=payload.n,
            size=payload.size,
            response_format=payload.response_format,
            output_format=payload.output_format,
            image=image,
            mask=mask,
            extra=extra,
        ),
        ctx=ctx,
        db=db,
        run_async=payload.run_async,
        response=response,
    )
    return ImageEditRead(
        run_id=run_id,
        model=model,
        status=run_status,
        mask_convention=MASK_CONVENTION,
        data=data,
    )
