"""Public schemas for governed conversation attachments."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentRead(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    thread_id: str | None
    filename: str
    content_type: str
    size_bytes: int
    checksum: str
    status: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
