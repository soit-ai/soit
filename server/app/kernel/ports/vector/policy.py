""" policy

Vector port policies: timeout/retry/rate-limit/audit.
"""

from typing import Any

from app.kernel.commons.errors import TimeoutError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.vector import VectorDocument, VectorQuery, VectorQueryMatch
from app.kernel.ports.common.policy import (
    error_details,
    resolve_run_id,
    run_with_timeout_retry,
)
from app.kernel.ports.vector.interface import VectorPort, VectorQueryResult
from app.kernel.runtime.runs.writer import TraceWriter


def _resolve_run_id(kwargs: dict[str, Any], ctx: RequestContext) -> str:
    return resolve_run_id(kwargs, ctx)


def _error_details(exc: Exception) -> dict[str, Any]:
    return error_details(exc)

class VectorPolicyGateway(VectorPort):
    """Vector port with policy enforcement."""

    def __init__(
        self,
        gateway: VectorPort,
        ctx: RequestContext,
        trace_writer: TraceWriter | None = None,
        timeout_seconds: int = 30,
        max_retries: int = 2,
    ):
        """Initialize policy gateway.

        Args:
            gateway: Underlying vector gateway.
            ctx: Request context.
            trace_writer: Optional trace writer.
            timeout_seconds: Request timeout.
            max_retries: Maximum retries.
        """
        self.gateway = gateway
        self.ctx = ctx
        self.trace_writer = trace_writer
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    async def ensure_collection(
        self,
        collection: str,
        dimension: int,
        metric_type: str,
        metadata_schema: dict[str, Any] | None = None,
        *,
        index_ref: str | None = None,
        run_id: str | None = None,
    ) -> None:
        """Ensure collection with policy enforcement."""
        kwargs = {"run_id": run_id, "index_ref": index_ref}
        step = None
        if self.trace_writer:
            resolved_run_id = _resolve_run_id(kwargs, self.ctx)
            if not resolved_run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=resolved_run_id,
                step_type="io",
                input_summary=f"collection={collection}, dimension={dimension}",
            )
            self.trace_writer.update_step_status(step.id, "running")

        start_time = utc_now()
        try:
            async def _ensure_collection():
                return await self.gateway.ensure_collection(
                    collection=collection,
                    dimension=dimension,
                    metric_type=metric_type,
                    metadata_schema=metadata_schema,
                    index_ref=index_ref,
                    run_id=run_id,
                )

            await run_with_timeout_retry(
                _ensure_collection,
                timeout_seconds=self.timeout_seconds,
                max_retries=1,
                timeout_factory=lambda: TimeoutError(
                    f"Vector collection ensure timed out after {self.timeout_seconds} seconds",
                    {"timeout_seconds": self.timeout_seconds, "collection": collection},
                ),
            )
            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={"latency_ms": elapsed_ms},
                )
        except TimeoutError as exc:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="VECTOR_COLLECTION_ERROR",
                    error_message=str(exc),
                    error_details=_error_details(exc),
                )
            raise
        except Exception as exc:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="VECTOR_COLLECTION_ERROR",
                    error_message=str(exc),
                    error_details=_error_details(exc),
                )
            raise

    async def query(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> VectorQueryResult:
        """Query vectors with policy enforcement."""
        query_contract = VectorQuery(
            collection=collection,
            vector=vector,
            top_k=top_k,
            filter=filter,
        )
        step = None
        if self.trace_writer:
            run_id = _resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=_resolve_run_id(kwargs, self.ctx),
                step_type="retrieval",
                input_summary=f"collection={query_contract.collection}, top_k={query_contract.top_k}",
            )
            self.trace_writer.update_step_status(step.id, "running")

        start_time = utc_now()
        try:
            async def _query():
                return await self.gateway.query(
                    collection=query_contract.collection,
                    vector=query_contract.vector,
                    top_k=query_contract.top_k,
                    filter=query_contract.filter,
                    **kwargs,
                )

            result = await run_with_timeout_retry(
                _query,
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
                timeout_factory=lambda: TimeoutError(
                    f"Vector query timed out after {self.timeout_seconds} seconds",
                    {"timeout_seconds": self.timeout_seconds, "collection": query_contract.collection}
                ),
                wait_min=1,
                wait_max=5,
            )
            matches = [
                VectorQueryMatch(
                    document=VectorDocument(
                        id=doc_id,
                        vector=(result.vectors or [None] * len(result.ids))[idx],
                        metadata=(result.metadata or [{}] * len(result.ids))[idx] or {},
                    ),
                    score=result.scores[idx],
                )
                for idx, doc_id in enumerate(result.ids)
            ]

            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "vector_count": len(matches),
                        "top_k": query_contract.top_k,
                        "latency_ms": elapsed_ms,
                    },
                )
                self.trace_writer.record_cost(
                    run_id=_resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="requests",
                    quantity=1,
                    provider="vector",
                )

            return result
        except Exception as e:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="VECTOR_QUERY_ERROR",
                    error_message=str(e),
                    error_details=_error_details(e),
                )
            raise

    async def insert(
        self,
        collection: str,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        """Insert vectors with policy enforcement."""
        step = None
        if self.trace_writer:
            run_id = _resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=run_id,
                step_type="io",
                input_summary=f"collection={collection}, vectors={len(vectors)}",
            )
            self.trace_writer.update_step_status(step.id, "running")

        start_time = utc_now()
        documents = [
            VectorDocument(
                id=doc_id,
                vector=vectors[idx],
                metadata=(metadata or [{}] * len(ids))[idx] or {},
            )
            for idx, doc_id in enumerate(ids)
        ]

        async def _insert():
            return await self.gateway.insert(
                collection=collection,
                vectors=[item.vector or [] for item in documents],
                ids=[item.id for item in documents],
                metadata=[item.metadata for item in documents] if metadata is not None else None,
                **kwargs,
            )

        try:
            await run_with_timeout_retry(
                _insert,
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
                timeout_factory=lambda: TimeoutError(
                    f"Vector insert timed out after {self.timeout_seconds} seconds",
                    {"timeout_seconds": self.timeout_seconds, "collection": collection}
                ),
                wait_min=1,
                wait_max=5,
            )
            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "vector_count": len(documents),
                        "latency_ms": elapsed_ms,
                    },
                )
                self.trace_writer.record_cost(
                    run_id=run_id,
                    step_id=step.id,
                    unit="vectors",
                    quantity=len(documents),
                    provider="vector",
                )
        except TimeoutError as exc:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="VECTOR_INSERT_ERROR",
                    error_message=str(exc),
                    error_details=_error_details(exc),
                )
            raise
        except Exception as exc:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="VECTOR_INSERT_ERROR",
                    error_message=str(exc),
                    error_details=_error_details(exc),
                )
            raise

    async def delete(
        self,
        collection: str,
        ids: list[str],
        **kwargs: Any,
    ) -> None:
        """Delete vectors with policy enforcement."""
        step = None
        if self.trace_writer:
            run_id = _resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=run_id,
                step_type="io",
                input_summary=f"collection={collection}, ids={len(ids)}",
            )
            self.trace_writer.update_step_status(step.id, "running")

        start_time = utc_now()
        documents = [VectorDocument(id=doc_id) for doc_id in ids]

        async def _delete():
            return await self.gateway.delete(
                collection=collection,
                ids=[item.id for item in documents],
                **kwargs,
            )

        try:
            await run_with_timeout_retry(
                _delete,
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
                timeout_factory=lambda: TimeoutError(
                    f"Vector delete timed out after {self.timeout_seconds} seconds",
                    {"timeout_seconds": self.timeout_seconds, "collection": collection}
                ),
                wait_min=1,
                wait_max=5,
            )
            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "delete_count": len(documents),
                        "latency_ms": elapsed_ms,
                    },
                )
                self.trace_writer.record_cost(
                    run_id=run_id,
                    step_id=step.id,
                    unit="vectors",
                    quantity=len(documents),
                    provider="vector",
                )
        except TimeoutError as exc:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="VECTOR_DELETE_ERROR",
                    error_message=str(exc),
                    error_details=_error_details(exc),
                )
            raise
        except Exception as exc:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="VECTOR_DELETE_ERROR",
                    error_message=str(exc),
                    error_details=_error_details(exc),
                )
            raise
