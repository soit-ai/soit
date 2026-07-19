"""Routes for governed conversation attachment uploads."""

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import Response

from app.api.v1.attachments.dependencies import get_attachment_service
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.attachments.schemas import AttachmentRead
from app.kernel.runtime.attachments.service import AttachmentService

router = APIRouter()
_SAFE_INLINE_IMAGE_TYPES = frozenset(
    {
        "image/avif",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)


@router.post("", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    file: UploadFile = File(...),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AttachmentService = Depends(get_attachment_service),
):
    """Validate and persist one conversation attachment in governed storage."""

    del ctx
    data = await file.read(AttachmentService.MAX_FILE_SIZE + 1)
    attachment = await service.upload(
        filename=file.filename or "attachment",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    return AttachmentRead.model_validate(attachment)


@router.get("/{attachment_id}", response_model=AttachmentRead)
async def get_attachment(
    attachment_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AttachmentService = Depends(get_attachment_service),
):
    del ctx
    return AttachmentRead.model_validate(service.get(attachment_id))


@router.get("/{attachment_id}/content", response_class=Response)
async def download_attachment(
    attachment_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AttachmentService = Depends(get_attachment_service),
):
    del ctx
    attachment, data = await service.get_content(attachment_id)
    encoded_filename = quote(attachment.filename, safe="")
    disposition = (
        "inline" if attachment.content_type in _SAFE_INLINE_IMAGE_TYPES else "attachment"
    )
    return Response(
        content=data,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{encoded_filename}",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )
