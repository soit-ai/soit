""" service

Memory domain service.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.trace.writer import TraceWriter
from app.kernel.ports.llm.interface import LLMPort
from app.kernel.ports.vector.interface import VectorPort
from app.modules.memory.domain.models import MemoryItem
from app.modules.memory.application.schemas import MemoryCreate, MemoryQuery, MemorySearchResult
from app.modules.memory.infra.repository import MemoryRepository
from app.settings.settings import settings
from app.kernel.identity.guard import rbac_guard
from app.kernel.identity.permissions import RESOURCE_MEMORY


class MemoryService:
    """Memory service."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        memory_repo: MemoryRepository,
        llm_port: Optional[LLMPort] = None,
        vector_port: Optional[VectorPort] = None,
        trace_writer: Optional[TraceWriter] = None,
    ):
        self.db = db
        self.ctx = ctx
        self.memory_repo = memory_repo
        self.llm_port = llm_port
        self.vector_port = vector_port
        self.trace_writer = trace_writer

    def _resolve_memory_trace_subject(self, user_id: Optional[str] = None) -> tuple[str, str]:
        owner_id = user_id or self.ctx.user_id or self.ctx.workspace_id
        return owner_id, "memory:v1"

    def _resolve_memory_owner_id(self, *args, **kwargs) -> str:
        """Resolve memory resource id for RBAC checks."""
        data = kwargs.get("data")
        if data is None and len(args) > 1:
            data = args[1]
        user_id = None
        if data is not None and hasattr(data, "user_id"):
            user_id = getattr(data, "user_id")
        return user_id or self.ctx.user_id

    def _collection_name(self) -> str:
        return f"mem_{self.ctx.tenant_id}_{self.ctx.workspace_id}"

    @rbac_guard(RESOURCE_MEMORY, "create", resource_id_resolver=_resolve_memory_owner_id)
    async def create_memory(self, data: MemoryCreate, run_id: Optional[str] = None) -> MemoryItem:
        """Create a memory item and optionally index it."""
        from app.kernel.specs.validator import validator

        validator.validate_memory_spec(data.model_dump())
        created_run = False
        if self.trace_writer and not run_id:
            summary = data.content_summary or str(data.content)
            subject_id, subject_version_id = self._resolve_memory_trace_subject(data.user_id)
            run = self.trace_writer.create_run(
                mode="memory_write",
                kind="batch",
                subject_kind="memory",
                subject_id=subject_id,
                subject_version_id=subject_version_id,
                input_summary=summary[:8192],
            )
            run_id = run.id
            created_run = True
            self.trace_writer.update_run_status(run_id, "running")

        memory = MemoryItem(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            user_id=data.user_id or self.ctx.user_id,
            memory_type=data.memory_type,
            content=data.content,
            content_summary=data.content_summary,
            metadata_json=data.metadata_json,
            tags=data.tags,
        )
        step_id = None
        if self.trace_writer and run_id:
            step = self.trace_writer.create_step(
                run_id=run_id,
                step_type="memory_write",
                input_summary="create_memory",
            )
            step_id = step.id
            self.trace_writer.update_step_status(step_id, "running")

        try:
            memory = self.memory_repo.create(memory)
            if self.llm_port and self.vector_port:
                text = data.content_summary or str(data.content)
                embedding_response = await self.llm_port.embed(
                    texts=[text],
                    model=settings.memory_embedding_model_ref,
                    run_id=run_id,
                )
                embeddings = embedding_response.embeddings
                if embeddings:
                    await self.vector_port.insert(
                        collection=self._collection_name(),
                        vectors=[embeddings[0]],
                        ids=[memory.id],
                        metadata=[{
                            "memory_type": memory.memory_type,
                            "user_id": memory.user_id,
                            "summary": memory.content_summary,
                        }],
                        run_id=run_id,
                    )
                    memory.vector_ref = memory.id
                    memory.updated_at = utc_now()
                    self.db.commit()
                    self.db.refresh(memory)

            if step_id and self.trace_writer:
                self.trace_writer.update_step_status(step_id, "succeeded")
            if created_run and self.trace_writer:
                self.trace_writer.update_run_status(
                    run_id,
                    "succeeded",
                    output_summary=f"memory_id={memory.id}",
                )
            return memory
        except Exception as exc:
            if step_id and self.trace_writer:
                self.trace_writer.update_step_status(
                    step_id,
                    "failed",
                    output_summary=str(exc)[:1024],
                )
            if created_run and self.trace_writer:
                self.trace_writer.update_run_status(
                    run_id,
                    "failed",
                    output_summary=str(exc)[:8192],
                )
            raise

    @rbac_guard(RESOURCE_MEMORY, "run", resource_id_resolver=_resolve_memory_owner_id)
    async def query_memory(
        self,
        data: MemoryQuery,
        run_id: Optional[str] = None,
    ) -> List[MemorySearchResult]:
        """Query memory items using vector similarity."""
        if not self.llm_port or not self.vector_port:
            raise ValidationError("Memory query requires LLM and vector ports")
        created_run = False
        if self.trace_writer and not run_id:
            subject_id, subject_version_id = self._resolve_memory_trace_subject(data.user_id)
            run = self.trace_writer.create_run(
                mode="memory_query",
                kind="tool",
                subject_kind="memory",
                subject_id=subject_id,
                subject_version_id=subject_version_id,
                input_summary=data.query[:8192],
            )
            run_id = run.id
            created_run = True
            self.trace_writer.update_run_status(run_id, "running")

        step_id = None
        if self.trace_writer and run_id:
            step = self.trace_writer.create_step(
                run_id=run_id,
                step_type="other",
                input_summary="query_memory",
            )
            step_id = step.id
            self.trace_writer.update_step_status(step_id, "running")

        try:
            embedding_response = await self.llm_port.embed(
                texts=[data.query],
                model=settings.memory_embedding_model_ref,
                run_id=run_id,
            )
            embeddings = embedding_response.embeddings
            if not embeddings:
                return []

            results = await self.vector_port.query(
                collection=self._collection_name(),
                vector=embeddings[0],
                top_k=data.top_k,
                include_metadata=True,
                run_id=run_id,
            )

            scores_map: Dict[str, float] = {
                memory_id: score for memory_id, score in zip(results.ids, results.scores)
            }
            items = self.memory_repo.list_by_ids(list(scores_map.keys()))

            filtered: List[MemoryItem] = []
            for item in items:
                if item.deleted_at is not None:
                    continue
                if data.memory_type and item.memory_type != data.memory_type:
                    continue
                if data.user_id and item.user_id != data.user_id:
                    continue
                filtered.append(item)

            ordered = sorted(filtered, key=lambda i: scores_map.get(i.id, 0.0), reverse=True)
            output = [
                MemorySearchResult(memory=item, score=scores_map.get(item.id, 0.0))
                for item in ordered
            ]

            if step_id and self.trace_writer:
                self.trace_writer.update_step_status(
                    step_id,
                    "succeeded",
                    output_summary=f"results={len(output)}",
                )
            if created_run and self.trace_writer:
                self.trace_writer.update_run_status(
                    run_id,
                    "succeeded",
                    output_summary=f"results={len(output)}",
                )
            return output
        except Exception as exc:
            if step_id and self.trace_writer:
                self.trace_writer.update_step_status(
                    step_id,
                    "failed",
                    output_summary=str(exc)[:1024],
                )
            if created_run and self.trace_writer:
                self.trace_writer.update_run_status(
                    run_id,
                    "failed",
                    output_summary=str(exc)[:8192],
                )
            raise

    @rbac_guard(RESOURCE_MEMORY, "read", resource_id_resolver=_resolve_memory_owner_id)
    async def list_memories(self, limit: int = 20, offset: int = 0) -> List[MemoryItem]:
        """List memories."""
        return self.memory_repo.list(limit=limit, offset=offset)

    @rbac_guard(RESOURCE_MEMORY, "read", resource_id_arg="memory_id")
    async def get_memory(self, memory_id: str) -> MemoryItem:
        """Get memory by id."""
        memory = self.memory_repo.get_by_id(memory_id)
        if not memory or memory.deleted_at is not None:
            raise NotFoundError(f"Memory not found: {memory_id}")
        return memory

    @rbac_guard(RESOURCE_MEMORY, "delete", resource_id_arg="memory_id")
    async def delete_memory(self, memory_id: str, run_id: Optional[str] = None) -> None:
        """Soft delete memory and remove vector."""
        memory = self.get_memory(memory_id)
        memory.deleted_at = utc_now()
        memory.updated_at = utc_now()
        self.db.commit()

        if self.vector_port:
            created_run = False
            if self.trace_writer and not run_id:
                subject_id, subject_version_id = self._resolve_memory_trace_subject(memory.user_id)
                run = self.trace_writer.create_run(
                    mode="memory_delete",
                    kind="batch",
                    subject_kind="memory",
                    subject_id=subject_id,
                    subject_version_id=subject_version_id,
                    input_summary=f"memory_id={memory_id}",
                )
                run_id = run.id
                created_run = True
                self.trace_writer.update_run_status(run_id, "running")

            try:
                await self.vector_port.delete(
                    collection=self._collection_name(),
                    ids=[memory.id],
                    run_id=run_id,
                )
                if created_run and self.trace_writer:
                    self.trace_writer.update_run_status(
                        run_id,
                        "succeeded",
                        output_summary=f"memory_id={memory_id}",
                    )
            except Exception as exc:
                if created_run and self.trace_writer:
                    self.trace_writer.update_run_status(
                        run_id,
                        "failed",
                        output_summary=str(exc)[:8192],
                    )
                raise
