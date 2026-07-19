"""Scoped persistence for conversation attachments."""

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.attachments import Attachment


class AttachmentRepository:
    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def create(self, attachment: Attachment) -> Attachment:
        attachment.tenant_id = self.ctx.tenant_id
        attachment.workspace_id = self.ctx.workspace_id
        attachment.created_by = self.ctx.user_id
        self.db.add(attachment)
        self.db.flush()
        self.db.refresh(attachment)
        return attachment

    def get(self, attachment_id: str) -> Attachment | None:
        query = select(Attachment).where(
            and_(
                Attachment.id == attachment_id,
                Attachment.tenant_id == self.ctx.tenant_id,
                Attachment.workspace_id == self.ctx.workspace_id,
            )
        )
        result = self.db.exec(query).first()
        return result if isinstance(result, Attachment) else result[0] if result else None

    def require(self, attachment_id: str) -> Attachment:
        attachment = self.get(attachment_id)
        if attachment is None:
            raise NotFoundError(f"Attachment not found: {attachment_id}")
        return attachment

    def require_for_update(self, attachment_id: str) -> Attachment:
        """Lock one scoped attachment before binding it to a conversation."""

        query = (
            select(Attachment)
            .where(
                and_(
                    Attachment.id == attachment_id,
                    Attachment.tenant_id == self.ctx.tenant_id,
                    Attachment.workspace_id == self.ctx.workspace_id,
                )
            )
            .with_for_update()
        )
        attachment = self.db.execute(query).scalars().first()
        if attachment is None:
            raise NotFoundError(f"Attachment not found: {attachment_id}")
        return attachment

    def update(self, attachment: Attachment) -> Attachment:
        attachment.updated_at = utc_now()
        self.db.add(attachment)
        self.db.flush()
        self.db.refresh(attachment)
        return attachment
