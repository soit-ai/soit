"""Governed object-storage lifecycle for conversation attachments."""

from __future__ import annotations

import hashlib
from pathlib import PurePath
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.runtime.attachments.repository import AttachmentRepository
from app.kernel.runtime.db.models.attachments import Attachment
from app.kernel.runtime.db.models.threads import Thread


class AttachmentService:
    MAX_FILE_SIZE = 25 * 1024 * 1024
    MAX_TEXT_CONTEXT_SIZE = 1024 * 1024
    MAX_ATTACHMENTS_PER_MESSAGE = 10
    MAX_TOTAL_TEXT_CONTEXT_SIZE = 2 * 1024 * 1024
    _BLOCKED_SUFFIXES = {
        ".bat",
        ".cmd",
        ".com",
        ".dll",
        ".exe",
        ".js",
        ".msi",
        ".ps1",
        ".scr",
        ".sh",
        ".vbs",
    }
    _ALLOWED_APPLICATION_TYPES = {
        "application/json",
        "application/msword",
        "application/pdf",
        "application/rtf",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/xml",
        "application/zip",
    }

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        *,
        storage_port: StoragePort,
        repository: AttachmentRepository | None = None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.storage_port = storage_port
        self.repository = repository or AttachmentRepository(db, ctx)

    @classmethod
    def _validate(cls, filename: str, content_type: str, data: bytes) -> tuple[str, str]:
        normalized_name = PurePath(filename or "attachment").name.strip()
        if not normalized_name or normalized_name in {".", ".."}:
            raise ValidationError("Attachment filename is invalid")
        if len(normalized_name) > 255:
            raise ValidationError("Attachment filename is too long")
        suffix = PurePath(normalized_name.lower()).suffix
        normalized_type = (content_type or "application/octet-stream").split(";", 1)[0].lower()
        if suffix in cls._BLOCKED_SUFFIXES or data.startswith(b"MZ"):
            raise ValidationError("Executable attachments are not allowed")
        allowed = (
            normalized_type.startswith("image/")
            or normalized_type.startswith("text/")
            or normalized_type in cls._ALLOWED_APPLICATION_TYPES
        )
        if not allowed:
            raise ValidationError(f"Attachment MIME type is not allowed: {normalized_type}")
        if not data:
            raise ValidationError("Attachment cannot be empty")
        if len(data) > cls.MAX_FILE_SIZE:
            raise ValidationError(
                f"Attachment exceeds the {cls.MAX_FILE_SIZE // (1024 * 1024)} MiB limit"
            )
        return normalized_name, normalized_type

    async def upload(self, *, filename: str, content_type: str, data: bytes) -> Attachment:
        filename, content_type = self._validate(filename, content_type, data)
        checksum = f"sha256:{hashlib.sha256(data).hexdigest()}"
        attachment = Attachment(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(data),
            checksum=checksum,
            storage_key="pending",
            status="uploading",
        )
        attachment = self.repository.create(attachment)
        attachment.storage_key = (
            f"attachments/{self.ctx.tenant_id}/{self.ctx.workspace_id}/{attachment.id}/content"
        )
        try:
            await self.storage_port.put(
                attachment.storage_key,
                data,
                content_type=content_type,
                metadata={"attachment_id": attachment.id, "checksum": checksum},
            )
        except Exception:
            attachment.status = "failed"
            self.repository.update(attachment)
            self.db.commit()
            raise
        attachment.status = "ready"
        attachment = self.repository.update(attachment)
        self.db.commit()
        return attachment

    def get(self, attachment_id: str) -> Attachment:
        return self.repository.require(attachment_id)

    async def get_content(self, attachment_id: str) -> tuple[Attachment, bytes]:
        attachment = self.repository.require(attachment_id)
        if attachment.status != "ready":
            raise ValidationError(f"Attachment is not ready: {attachment.id}")
        return attachment, await self.storage_port.get(attachment.storage_key)

    def validate_thread_target(self, thread_id: str, *, agent_id: str | None) -> Thread:
        """Validate the scoped conversation before any attachment is consumed."""

        thread = self.db.execute(
            select(Thread).where(
                and_(
                    Thread.id == thread_id,
                    Thread.tenant_id == self.ctx.tenant_id,
                    Thread.workspace_id == self.ctx.workspace_id,
                    Thread.deleted_at.is_(None),
                )
            )
        ).scalars().first()
        if thread is None:
            raise NotFoundError(f"Thread not found: {thread_id}")
        if thread.agent_id and thread.agent_id != agent_id:
            raise ValidationError(f"Thread {thread.id} does not belong to the selected Agent")
        return thread

    async def resolve_for_message(
        self,
        attachment_ids: list[str],
        *,
        thread_id: str,
    ) -> list[dict[str, Any]]:
        attachment_ids = list(dict.fromkeys(attachment_ids))
        if len(attachment_ids) > self.MAX_ATTACHMENTS_PER_MESSAGE:
            raise ValidationError(
                f"A message can include at most {self.MAX_ATTACHMENTS_PER_MESSAGE} attachments"
            )
        descriptors: list[dict[str, Any]] = []
        total_context_size = 0
        for attachment_id in sorted(attachment_ids):
            attachment = self.repository.require_for_update(attachment_id)
            if attachment.status != "ready":
                raise ValidationError(f"Attachment is not ready: {attachment.id}")
            if attachment.thread_id and attachment.thread_id != thread_id:
                raise ValidationError("Attachment is already bound to another thread")
            if attachment.thread_id is None:
                attachment.thread_id = thread_id
                self.repository.update(attachment)
            descriptor: dict[str, Any] = {
                "id": attachment.id,
                "name": attachment.filename,
                "filename": attachment.filename,
                "type": "image" if attachment.content_type.startswith("image/") else "document",
                "content_type": attachment.content_type,
                "size": attachment.size_bytes,
                "checksum": attachment.checksum,
            }
            if (
                attachment.content_type.startswith("text/")
                or attachment.content_type in {"application/json", "application/xml"}
            ) and attachment.size_bytes <= self.MAX_TEXT_CONTEXT_SIZE:
                if (
                    total_context_size + attachment.size_bytes
                    > self.MAX_TOTAL_TEXT_CONTEXT_SIZE
                ):
                    raise ValidationError(
                        "Attachment text context exceeds the aggregate message limit"
                    )
                content = await self.storage_port.get(attachment.storage_key)
                total_context_size += len(content)
                descriptor["_context_text"] = content.decode("utf-8", errors="replace")
            descriptors.append(descriptor)
        descriptors_by_id = {str(item["id"]): item for item in descriptors}
        return [descriptors_by_id[attachment_id] for attachment_id in attachment_ids]
