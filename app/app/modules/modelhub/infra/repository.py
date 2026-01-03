""" repository

ModelHub domain repository.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc

from app.infra.db.repository import Repository
from app.kernel.contracts.context import RequestContext
from app.modules.modelhub.domain.models import Model
from app.kernel.commons.errors import NotFoundError


class ModelRepository(Repository[Model]):
    """Repository for Model model."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize model repository.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(Model, db, ctx)
    
    def get_by_name(self, name: str) -> Optional[Model]:
        """Get model by name.
        
        Args:
            name: Model name.
            
        Returns:
            Model instance or None if not found.
        """
        query = select(Model).where(
            and_(
                Model.tenant_id == self.ctx.tenant_id,
                Model.workspace_id == self.ctx.workspace_id,
                Model.name == name,
            )
        )
        return self.db.exec(query).first()
    
    def get_by_model_ref(self, model_ref: str) -> Optional[Model]:
        """Get model by model reference.
        
        Args:
            model_ref: Model reference.
            
        Returns:
            Model instance or None if not found.
        """
        query = select(Model).where(
            and_(
                Model.tenant_id == self.ctx.tenant_id,
                Model.workspace_id == self.ctx.workspace_id,
                Model.model_ref == model_ref,
            )
        )
        return self.db.exec(query).first()
    
    def list(
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
        query = select(Model).where(
            and_(
                Model.tenant_id == self.ctx.tenant_id,
                Model.workspace_id == self.ctx.workspace_id,
            )
        )
        
        if provider:
            query = query.where(Model.provider == provider)
        
        query = query.order_by(desc(Model.created_at)).offset(offset).limit(limit)
        
        return list(self.db.exec(query).all())
