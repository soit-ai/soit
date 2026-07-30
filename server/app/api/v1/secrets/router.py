"""router

Secrets API routes.
"""


from fastapi import APIRouter, Depends, status

from app.api.v1.permissions import (
    require_workspace_governance_ctx,
    require_workspace_read_ctx,
)
from app.api.v1.secrets.dependencies import get_secrets_service
from app.api.v1.secrets.handlers import SecretHandlers
from app.kernel.contracts.context import RequestContext
from app.modules.secrets.application.schemas import (
    SecretCreate,
    SecretResponse,
    SecretTestResponse,
    SecretUpdate,
)
from app.modules.secrets.application.service import SecretsService

router = APIRouter()


@router.get("", response_model=list[SecretResponse])
async def list_secrets(
    limit: int = 50,
    offset: int = 0,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: SecretsService = Depends(get_secrets_service),
):
    """List secrets in workspace."""
    handlers = SecretHandlers(service)
    return await handlers.list_secrets(ctx, limit=limit, offset=offset)


@router.get("/{secret_id}", response_model=SecretResponse)
async def get_secret(
    secret_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: SecretsService = Depends(get_secrets_service),
):
    """Get secret metadata."""
    handlers = SecretHandlers(service)
    return await handlers.get_secret(ctx, secret_id)


@router.post("", response_model=SecretResponse, status_code=status.HTTP_201_CREATED)
async def create_secret(
    data: SecretCreate,
    ctx: RequestContext = Depends(require_workspace_governance_ctx),
    service: SecretsService = Depends(get_secrets_service),
):
    """Create a secret."""
    handlers = SecretHandlers(service)
    return await handlers.create_secret(ctx, data)


@router.patch("/{secret_id}", response_model=SecretResponse)
async def update_secret(
    secret_id: str,
    data: SecretUpdate,
    ctx: RequestContext = Depends(require_workspace_governance_ctx),
    service: SecretsService = Depends(get_secrets_service),
):
    """Update secret metadata or rotate value."""
    handlers = SecretHandlers(service)
    return await handlers.update_secret(ctx, secret_id, data)


@router.delete("/{secret_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(
    secret_id: str,
    ctx: RequestContext = Depends(require_workspace_governance_ctx),
    service: SecretsService = Depends(get_secrets_service),
):
    """Delete a secret."""
    handlers = SecretHandlers(service)
    await handlers.delete_secret(ctx, secret_id)


@router.post("/{secret_id}/test", response_model=SecretTestResponse)
async def test_secret(
    secret_id: str,
    ctx: RequestContext = Depends(require_workspace_governance_ctx),
    service: SecretsService = Depends(get_secrets_service),
):
    """Test secret reference resolution."""
    handlers = SecretHandlers(service)
    return await handlers.test_secret(ctx, secret_id)
