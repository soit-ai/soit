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
    from app.modules.domains.dataset.pipeline import DocumentPipeline
    from app.modules.domains.dataset.retrieval import RetrievalService
    from app.modules.domains.dataset.embedding import EmbeddingService
    from app.modules.domains.dataset.index_builder import IndexBuilder
    from app.kernel.trace.writer import TraceWriter
    from app.kernel.di import get_container
    
    # Initialize trace writer
    trace_writer = TraceWriter(db, ctx)
    
    # Get gateways from container (with policy enforcement)
    container = get_container()
    storage_gateway = container.get_storage_gateway(
        ctx=ctx,
        trace_writer=trace_writer,
    )
    vector_gateway = container.get_vector_gateway(
        ctx=ctx,
        trace_writer=trace_writer,
    )
    llm_gateway = container.get_llm_gateway(
        ctx=ctx,
        trace_writer=trace_writer,
    )
    
    # Initialize embedding service
    embedding_service = EmbeddingService(llm_gateway)
    
    # Initialize index builder
    index_builder = IndexBuilder(
        db=db,
        ctx=ctx,
        vector_gateway=vector_gateway,
        embedding_service=embedding_service,
        storage_gateway=storage_gateway,
    )
    
    # Initialize document pipeline
    pipeline = DocumentPipeline(
        db=db,
        ctx=ctx,
        storage_gateway=storage_gateway,
        trace_writer=trace_writer,
        embedding_service=embedding_service,
        index_builder=index_builder,
    )
    
    # Initialize retrieval service
    retrieval_service = RetrievalService(
        db=db,
        ctx=ctx,
        vector_gateway=vector_gateway,
        llm_gateway=llm_gateway,
        embedding_service=embedding_service,
        storage_gateway=storage_gateway,
    )
    
    return DatasetService(db, ctx, pipeline, retrieval_service)

