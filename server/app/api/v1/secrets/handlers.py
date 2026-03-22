"""handlers

Secrets request handlers.
"""

from typing import Optional, List

from app.kernel.contracts.context import RequestContext
from app.modules.secrets.application.service import SecretsService
from app.modules.secrets.application.schemas import (
    SecretCreate,
    SecretUpdate,
    SecretResponse,
    SecretTestResponse,
)


class SecretHandlers:
    """Handlers for secrets API endpoints."""

    def __init__(self, service: SecretsService):
        self.service = service

    async def list_secrets(
        self,
        ctx: RequestContext,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> List[SecretResponse]:
        secrets = await self.service.list_secrets(limit=limit, offset=offset)
        return [SecretResponse.model_validate(item) for item in secrets]

    async def get_secret(
        self,
        ctx: RequestContext,
        secret_id: str,
    ) -> SecretResponse:
        secret = await self.service.get_secret(secret_id)
        return SecretResponse.model_validate(secret)

    async def create_secret(
        self,
        ctx: RequestContext,
        data: SecretCreate,
    ) -> SecretResponse:
        secret = await self.service.create_secret(data)
        return SecretResponse.model_validate(secret)

    async def update_secret(
        self,
        ctx: RequestContext,
        secret_id: str,
        data: SecretUpdate,
    ) -> SecretResponse:
        secret = await self.service.update_secret(secret_id, data)
        return SecretResponse.model_validate(secret)

    async def delete_secret(
        self,
        ctx: RequestContext,
        secret_id: str,
    ) -> None:
        await self.service.delete_secret(secret_id)

    async def test_secret(
        self,
        ctx: RequestContext,
        secret_id: str,
    ) -> SecretTestResponse:
        await self.service.test_secret(secret_id)
        return SecretTestResponse(ok=True, message="ok")
