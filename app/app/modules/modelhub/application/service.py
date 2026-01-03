""" service

ModelHub domain service.
"""

from typing import Optional, List
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.modules.modelhub.domain.models import Model
from app.modules.modelhub.application.ports import ModelRepositoryPort
from app.modules.modelhub.application.schemas import ModelCreate, ModelUpdate


class ModelHubService:
    """ModelHub domain service."""
    
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        model_repo: ModelRepositoryPort,
    ):
        """Initialize model hub service.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        self.db = db
        self.ctx = ctx
        self.model_repo = model_repo

    def create_model(self, model_in: ModelCreate) -> Model:
        """Create a new model.
        
        Args:
            model_in: Model creation schema.
            
        Returns:
            Created Model instance.
            
        Raises:
            ValidationError: If model name or model_ref already exists.
        """
        # Check if name already exists
        existing = self.model_repo.get_by_name(model_in.name)
        if existing:
            raise ValidationError(f"Model with name '{model_in.name}' already exists")
        
        # Check if model_ref already exists
        existing_ref = self.model_repo.get_by_model_ref(model_in.model_ref)
        if existing_ref:
            raise ValidationError(f"Model with reference '{model_in.model_ref}' already exists")
        
        model = Model(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            name=model_in.name,
            provider=model_in.provider,
            model_ref=model_in.model_ref,
            description=model_in.description,
            capabilities_json=model_in.capabilities_json,
            config_json=model_in.config_json,
            metadata_json=model_in.metadata_json,
            created_by=self.ctx.user_id,
        )
        
        return self.model_repo.create(model)
    
    def get_model(self, model_id: str) -> Model:
        """Get model by ID.
        
        Args:
            model_id: Model ID.
            
        Returns:
            Model instance.
            
        Raises:
            NotFoundError: If model not found.
        """
        model = self.model_repo.get_by_id(model_id)
        if not model:
            raise NotFoundError(f"Model not found: {model_id}")
        return model
    
    def list_models(
        self,
        provider: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Model]:
        """List models.
        
        Args:
            provider: Optional provider filter.
            limit: Maximum number of models.
            offset: Offset for pagination.
            
        Returns:
            List of Model instances.
        """
        return self.model_repo.list(provider=provider, limit=limit, offset=offset)
    
    def update_model(self, model_id: str, model_in: ModelUpdate) -> Model:
        """Update model.
        
        Args:
            model_id: Model ID.
            model_in: Model update schema.
            
        Returns:
            Updated Model instance.
            
        Raises:
            NotFoundError: If model not found.
            ValidationError: If new name conflicts with existing model.
        """
        model = self.get_model(model_id)
        
        # Check name conflict if name is being changed
        if model_in.name and model_in.name != model.name:
            existing = self.model_repo.get_by_name(model_in.name)
            if existing and existing.id != model_id:
                raise ValidationError(f"Model with name '{model_in.name}' already exists")
            model.name = model_in.name
        
        if model_in.description is not None:
            model.description = model_in.description
        
        if model_in.capabilities_json is not None:
            model.capabilities_json = model_in.capabilities_json
        
        if model_in.config_json is not None:
            model.config_json = model_in.config_json
        
        if model_in.metadata_json is not None:
            model.metadata_json = model_in.metadata_json
        
        model.updated_at = utc_now()
        
        self.db.commit()
        self.db.refresh(model)
        return model
    
    def delete_model(self, model_id: str) -> None:
        """Delete model.
        
        Args:
            model_id: Model ID.
            
        Raises:
            NotFoundError: If model not found.
        """
        model = self.get_model(model_id)
        self.db.delete(model)
        self.db.commit()
