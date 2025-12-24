""" dependencies

Dataset entry dependencies (ctx/auth/policy).
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.domains.dataset.service import DatasetService
from app.modules.domains.dataset.pipeline import DocumentPipeline
from app.modules.domains.dataset.retrieval import RetrievalService


def get_dataset_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> DatasetService:
    """Get dataset service instance.
    
    Args:
        ctx: Request context.
        db: Database session.
        
    Returns:
        DatasetService instance.
    """
    # TODO: Initialize pipeline and retrieval service with proper dependencies
    # For now, create placeholder instances
    # In production, these should be properly initialized via dependency injection
    
    # Create minimal service instance
    # Note: This is a simplified version - in production, use proper DI
    from app.modules.domains.dataset.pipeline import DocumentPipeline
    from app.modules.domains.dataset.retrieval import RetrievalService
    
    # Create placeholder instances - these would normally be injected
    # For now, pass None and let the service handle it gracefully
    pipeline = None  # TODO: Initialize with proper dependencies
    retrieval_service = None  # TODO: Initialize with proper dependencies
    
    return DatasetService(db, ctx, pipeline, retrieval_service)

