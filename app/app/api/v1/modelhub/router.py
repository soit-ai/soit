""" router

ModelHub API routes (FastAPI).
"""

from typing import Optional
from fastapi import APIRouter, Depends, status

from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.modelhub.application.service import ModelHubService
from app.modules.modelhub.application.schemas import (
    ModelCreate,
    ModelUpdate,
    ModelResponse,
)
from app.api.v1.modelhub.dependencies import get_modelhub_service
from app.api.v1.modelhub.handlers import ModelHubHandlers
from app.infra.db.pagination import PaginatedResponse


router = APIRouter()


@router.post("", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    model_in: ModelCreate,
    ctx: RequestContext = Depends(get_current_context),
    service: ModelHubService = Depends(get_modelhub_service),
):
    """Create a new model.
    
    Args:
        model_in: Model creation data.
        ctx: Request context.
        service: ModelHubService instance.
        
    Returns:
        Created model.
    """
    handlers = ModelHubHandlers(service)
    return await handlers.create_model(ctx, model_in)


@router.get("", response_model=PaginatedResponse[ModelResponse])
async def list_models(
    provider: Optional[str] = None,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(get_current_context),
    service: ModelHubService = Depends(get_modelhub_service),
):
    """List models.
    
    Args:
        provider: Optional provider filter.
        page_token: Optional page token.
        page_size: Page size.
        ctx: Request context.
        service: ModelHubService instance.
        
    Returns:
        Paginated models.
    """
    handlers = ModelHubHandlers(service)
    return await handlers.list_models(ctx, provider, page_token, page_size)


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: str,
    ctx: RequestContext = Depends(get_current_context),
    service: ModelHubService = Depends(get_modelhub_service),
):
    """Get model by ID.
    
    Args:
        model_id: Model ID.
        ctx: Request context.
        service: ModelHubService instance.
        
    Returns:
        Model details.
    """
    handlers = ModelHubHandlers(service)
    return await handlers.get_model(ctx, model_id)


@router.put("/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: str,
    model_in: ModelUpdate,
    ctx: RequestContext = Depends(get_current_context),
    service: ModelHubService = Depends(get_modelhub_service),
):
    """Update model.
    
    Args:
        model_id: Model ID.
        model_in: Model update data.
        ctx: Request context.
        service: ModelHubService instance.
        
    Returns:
        Updated model.
    """
    handlers = ModelHubHandlers(service)
    return await handlers.update_model(ctx, model_id, model_in)


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: str,
    ctx: RequestContext = Depends(get_current_context),
    service: ModelHubService = Depends(get_modelhub_service),
):
    """Delete model.
    
    Args:
        model_id: Model ID.
        ctx: Request context.
        service: ModelHubService instance.
    """
    handlers = ModelHubHandlers(service)
    await handlers.delete_model(ctx, model_id)

