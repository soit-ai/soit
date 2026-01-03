""" handlers

ModelHub request handlers (thin orchestration).
"""

from typing import List, Optional

from app.kernel.contracts.context import RequestContext
from app.modules.modelhub.application.service import ModelHubService
from app.modules.modelhub.application.schemas import (
    ModelCreate,
    ModelUpdate,
    ModelResponse,
)
from app.infra.db.pagination import PaginatedResponse, parse_page_params


class ModelHubHandlers:
    """Handlers for ModelHub API endpoints."""
    
    def __init__(self, service: ModelHubService):
        """Initialize model hub handlers.
        
        Args:
            service: ModelHubService instance.
        """
        self.service = service
    
    async def create_model(
        self,
        ctx: RequestContext,
        model_in: ModelCreate,
    ) -> ModelResponse:
        """Create a new model.
        
        Args:
            ctx: Request context.
            model_in: Model creation schema.
            
        Returns:
            Created model.
        """
        model = self.service.create_model(model_in)
        return ModelResponse.model_validate(model)
    
    async def list_models(
        self,
        ctx: RequestContext,
        provider: Optional[str] = None,
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> PaginatedResponse[ModelResponse]:
        """List models.
        
        Args:
            ctx: Request context.
            provider: Optional provider filter.
            page_token: Optional page token.
            page_size: Page size.
            
        Returns:
            Paginated models.
        """
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        
        models = self.service.list_models(provider=provider, limit=limit, offset=offset)
        
        items = [ModelResponse.model_validate(m) for m in models]
        
        has_next = len(models) == limit
        next_offset = offset + len(models) if has_next else None
        
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )
    
    async def get_model(
        self,
        ctx: RequestContext,
        model_id: str,
    ) -> ModelResponse:
        """Get model by ID.
        
        Args:
            ctx: Request context.
            model_id: Model ID.
            
        Returns:
            Model details.
        """
        model = self.service.get_model(model_id)
        return ModelResponse.model_validate(model)
    
    async def update_model(
        self,
        ctx: RequestContext,
        model_id: str,
        model_in: ModelUpdate,
    ) -> ModelResponse:
        """Update model.
        
        Args:
            ctx: Request context.
            model_id: Model ID.
            model_in: Model update schema.
            
        Returns:
            Updated model.
        """
        model = self.service.update_model(model_id, model_in)
        return ModelResponse.model_validate(model)
    
    async def delete_model(
        self,
        ctx: RequestContext,
        model_id: str,
    ) -> None:
        """Delete model.
        
        Args:
            ctx: Request context.
            model_id: Model ID.
        """
        self.service.delete_model(model_id)

