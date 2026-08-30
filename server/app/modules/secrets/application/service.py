"""service

Secrets application service.
"""

from __future__ import annotations

from datetime import datetime

from app.kernel.commons.errors import KernelError, NotFoundError, ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.guard import workspace_guard
from app.kernel.ports.secrets.interface import SecretLocator, SecretValueStore
from app.modules.secrets.application.schemas import (
    SecretCreate,
    SecretResolutionSummary,
    SecretUpdate,
)
from app.modules.secrets.domain.models import Secret
from app.modules.secrets.infra.repository import SecretRepository


class SecretsService:
    """Secrets management service."""

    def __init__(
        self,
        ctx: RequestContext,
        repo: SecretRepository,
        value_store: SecretValueStore,
    ):
        self.ctx = ctx
        self.repo = repo
        self.value_store = value_store

    @workspace_guard("read")
    async def list_secrets(self, limit: int = 50, offset: int = 0) -> list[Secret]:
        """List secrets for workspace."""
        return self.repo.list(limit=limit, offset=offset)

    @workspace_guard("read")
    async def summarize_resolutions(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> SecretResolutionSummary:
        """Report how often secrets were resolved inside a window."""
        total, secrets = self.repo.resolution_counts(since=since, until=until)
        return SecretResolutionSummary(
            since=since,
            until=until,
            total=total,
            secrets=secrets,
        )

    @workspace_guard("read")
    async def get_secret(self, secret_id: str) -> Secret:
        """Get secret metadata by ID."""
        secret = self.repo.get_by_id(secret_id)
        if not secret:
            raise NotFoundError(f"Secret not found: {secret_id}")
        return secret

    @workspace_guard("write")
    async def create_secret(self, data: SecretCreate) -> Secret:
        """Create secret (store value in Vault and metadata in DB)."""
        if self.repo.get_by_name(data.name):
            raise ValidationError(f"Secret name already exists: {data.name}")

        from app.kernel.commons.ids import generate_secret_id
        secret_id = generate_secret_id()

        secret_ref = f"secret:{secret_id}"
        from app.kernel.commons.time import utc_now
        secret = Secret(
            id=secret_id,
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            name=data.name.strip(),
            description=data.description,
            secret_ref=secret_ref,
            last_rotated_at=utc_now(),
            created_by=self.ctx.user_id,
            updated_by=self.ctx.user_id,
        )

        secret = self.repo.create(secret)

        try:
            await self.value_store.set_secret_value(
                locator=SecretLocator(secret.secret_ref), value=data.value
            )
        except Exception as exc:
            # Roll back metadata if vault write fails.
            self.repo.soft_delete(secret, updated_by=self.ctx.user_id)
            raise KernelError("SECRETS_WRITE_FAILED", f"Failed to write secret: {str(exc)}")

        return secret

    @workspace_guard("write")
    async def update_secret(self, secret_id: str, data: SecretUpdate) -> Secret:
        """Update secret metadata and optionally rotate value."""
        secret = self.repo.get_by_id(secret_id)
        if not secret:
            raise NotFoundError(f"Secret not found: {secret_id}")

        if data.name and data.name.strip() != secret.name:
            if self.repo.get_by_name(data.name.strip()):
                raise ValidationError(f"Secret name already exists: {data.name.strip()}")

        if data.value is not None:
            try:
                await self.value_store.set_secret_value(
                    locator=SecretLocator(secret.secret_ref), value=data.value
                )
            except Exception as exc:
                raise KernelError("SECRETS_WRITE_FAILED", f"Failed to rotate secret: {str(exc)}")

        from app.kernel.commons.time import utc_now
        last_rotated_at = utc_now() if data.value is not None else None

        return self.repo.update(
            secret,
            name=data.name.strip() if data.name else None,
            description=data.description if data.description is not None else None,
            updated_by=self.ctx.user_id,
            last_rotated_at=last_rotated_at,
        )

    @workspace_guard("write")
    async def delete_secret(self, secret_id: str) -> None:
        """Delete secret from Vault and soft delete metadata."""
        secret = self.repo.get_by_id(secret_id)
        if not secret:
            raise NotFoundError(f"Secret not found: {secret_id}")

        try:
            await self.value_store.delete_secret_value(
                locator=SecretLocator(secret.secret_ref)
            )
        except Exception as exc:
            raise KernelError("SECRETS_DELETE_FAILED", f"Failed to delete secret: {str(exc)}")

        self.repo.soft_delete(secret, updated_by=self.ctx.user_id)

    @workspace_guard("write")
    async def test_secret(self, secret_id: str) -> None:
        """Test secret reference resolution."""
        secret = self.repo.get_by_id(secret_id)
        if not secret:
            raise NotFoundError(f"Secret not found: {secret_id}")
        try:
            await self.value_store.get_secret_value(
                locator=SecretLocator(secret.secret_ref)
            )
        except Exception as exc:
            raise KernelError("SECRETS_TEST_FAILED", f"Failed to resolve secret: {str(exc)}")
