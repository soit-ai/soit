""" dependencies

Dataset entry dependencies (ctx/auth/policy).
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.infra.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.dataset.application.service import DatasetService
from app.modules.dataset.runtime.pipeline import DocumentPipeline
from app.modules.dataset.runtime.retrieval import RetrievalService
from app.modules.dataset.infra.repository import DatasetRepository, DocumentRepository, ChunkRepository, IndexRepository



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

    from app.modules.dataset.runtime.embedding import EmbeddingService
    from app.modules.dataset.runtime.index_builder import IndexBuilder
    from app.kernel.trace.writer import TraceWriter
    from app.wiring import get_container
    
    # Initialize trace writer
    trace_writer = TraceWriter(db, ctx)
    
    # Get ports from container (with policy enforcement)
    container = get_container()
    storage_port = container.get_storage_port(
        ctx=ctx,
        trace_writer=trace_writer,
    )
    vector_port = container.get_vector_port(
        ctx=ctx,
        trace_writer=trace_writer,
    )
    llm_port = container.get_llm_port(
        ctx=ctx,
        trace_writer=trace_writer,
    )
    
    # Initialize embedding service
    embedding_service = EmbeddingService(llm_port)
    
    # Initialize index builder
    index_builder = IndexBuilder(
        db=db,
        ctx=ctx,
        vector_port=vector_port,
        embedding_service=embedding_service,
        storage_port=storage_port,
    )
    
    # Initialize document pipeline
    pipeline = DocumentPipeline(
        db=db,
        ctx=ctx,
        storage_port=storage_port,
        trace_writer=trace_writer,
        embedding_service=embedding_service,
        index_builder=index_builder,
    )
    
    # Initialize retrieval service
    retrieval_service = RetrievalService(
        db=db,
        ctx=ctx,
        vector_port=vector_port,
        llm_port=llm_port,
        embedding_service=embedding_service,
        storage_port=storage_port,
    )
    
    dataset_repo = DatasetRepository(db, ctx)
    document_repo = DocumentRepository(db, ctx)
    chunk_repo = ChunkRepository(db, ctx)
    index_repo = IndexRepository(db, ctx)

    return DatasetService(db, ctx, dataset_repo, document_repo, chunk_repo, index_repo, pipeline, retrieval_service)

