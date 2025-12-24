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
    from app.modules.domains.dataset.chunker import TextChunker
    from app.adapters.minio_storage import MinIOStorageGateway
    from app.adapters.milvus_vector import MilvusVectorGateway
    from app.adapters.openai_llm import OpenAILLMGateway
    from app.kernel.trace.writer import TraceWriter
    
    # Initialize gateways
    storage_gateway = MinIOStorageGateway()
    vector_gateway = MilvusVectorGateway()
    llm_gateway = OpenAILLMGateway()
    
    # Initialize trace writer
    trace_writer = TraceWriter(db, ctx)
    
    # Initialize embedding service
    embedding_service = EmbeddingService(llm_gateway, trace_writer)
    
    # Initialize chunker
    chunker = TextChunker()
    
    # Initialize document pipeline
    pipeline = DocumentPipeline(
        storage_gateway=storage_gateway,
        embedding_service=embedding_service,
        chunker=chunker,
        trace_writer=trace_writer,
    )
    
    # Initialize retrieval service
    retrieval_service = RetrievalService(
        vector_gateway=vector_gateway,
        embedding_service=embedding_service,
        trace_writer=trace_writer,
    )
    
    return DatasetService(db, ctx, pipeline, retrieval_service)

