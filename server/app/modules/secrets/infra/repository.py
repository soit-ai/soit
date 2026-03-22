"""repository

Secrets repository.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc

from app.infra.db.repository import Repository
from app.kernel.contracts.context import RequestContext
from app.modules.secrets.domain.models import Secret


class SecretRepository(Repository[Secret]):
    """Repository for Secret model."""

    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize secret repository."""
        super().__init__(Secret, db, ctx)

    def create(self, secret: Secret) -> Secret:
        """Create a secret metadata record."""
        self.db.add(secret)
        self.db.commit()
        self.db.refresh(secret)
        return secret

    def get_by_id(self, secret_id: str) -> Optional[Secret]:
        """Get secret by ID."""
        query = select(Secret).where(
            and_(
                Secret.id == secret_id,
                Secret.tenant_id == self.ctx.tenant_id,
                Secret.workspace_id == self.ctx.workspace_id,
                Secret.deleted_at.is_(None),
            )
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def get_by_name(self, name: str) -> Optional[Secret]:
        """Get secret by name."""
        query = select(Secret).where(
            and_(
                Secret.name == name,
                Secret.tenant_id == self.ctx.tenant_id,
                Secret.workspace_id == self.ctx.workspace_id,
                Secret.deleted_at.is_(None),
            )
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def list(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Secret]:
        """List secrets for workspace."""
        query = (
            select(Secret)
            .where(
                and_(
                    Secret.tenant_id == self.ctx.tenant_id,
                    Secret.workspace_id == self.ctx.workspace_id,
                    Secret.deleted_at.is_(None),
                )
            )
            .order_by(desc(Secret.updated_at))
            .offset(offset)
            .limit(limit)
        )
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)

    def update(
        self,
        secret: Secret,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        updated_by: Optional[str] = None,
        last_rotated_at: Optional["datetime"] = None,
    ) -> Secret:
        """Update secret metadata."""
        if name is not None:
            secret.name = name
        if description is not None:
            secret.description = description
        if updated_by is not None:
            secret.updated_by = updated_by
        if last_rotated_at is not None:
            secret.last_rotated_at = last_rotated_at

        from app.kernel.commons.time import utc_now
        secret.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(secret)
        return secret

    def soft_delete(self, secret: Secret, updated_by: Optional[str] = None) -> Secret:
        """Soft delete a secret record."""
        from app.kernel.commons.time import utc_now
        secret.deleted_at = utc_now()
        secret.updated_at = utc_now()
        if updated_by is not None:
            secret.updated_by = updated_by
        self.db.commit()
        self.db.refresh(secret)
        return secret
