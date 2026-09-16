"""Scoped persistence for conversation attachments."""

from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import NotFoundError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.attachments import Attachment


class AttachmentRepository:
    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def _scoped(self, attachment_id: str):
        return select(Attachment).where(
            and_(
                Attachment.id == attachment_id,
                Attachment.tenant_id == self.ctx.tenant_id,
                Attachment.workspace_id == self.ctx.workspace_id,
            )
        )

    async def create(self, attachment: Attachment) -> Attachment:
        attachment.tenant_id = self.ctx.tenant_id
        attachment.workspace_id = self.ctx.workspace_id
        attachment.created_by = self.ctx.user_id
        self.db.add(attachment)
        await self.db.flush()
        await self.db.refresh(attachment)
        return attachment

    async def get(self, attachment_id: str) -> Attachment | None:
        result = (await self.db.exec(self._scoped(attachment_id))).first()
        return result if isinstance(result, Attachment) else result[0] if result else None

    async def require(self, attachment_id: str) -> Attachment:
        attachment = await self.get(attachment_id)
        if attachment is None:
            raise NotFoundError(f"Attachment not found: {attachment_id}")
        return attachment

    async def require_for_update(self, attachment_id: str) -> Attachment:
        """Lock one scoped attachment before binding it to a conversation."""

        attachment = (
            await self.db.exec(self._scoped(attachment_id).with_for_update())
        ).scalars().first()
        if attachment is None:
            raise NotFoundError(f"Attachment not found: {attachment_id}")
        return attachment

    async def update(self, attachment: Attachment) -> Attachment:
        attachment.updated_at = utc_now()
        self.db.add(attachment)
        await self.db.flush()
        await self.db.refresh(attachment)
        return attachment
