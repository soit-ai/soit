""" repository

Scope-aware repository bases (tenant_id + workspace_id enforced).

`Repository` is the sync base that existing code inherits. `AsyncRepository`
is its `AsyncSession` counterpart; both share the scope and unwrap helpers so
a subclass moves between them by changing the base class and awaiting.
"""

from typing import Any, Generic, TypeVar

from sqlalchemy import and_, func
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext

ModelType = TypeVar("ModelType", bound=SQLModel)


class _ScopedRepositoryBase(Generic[ModelType]):
    """Scope filtering and row unwrapping shared by the sync and async bases."""

    def __init__(self, model: type[ModelType], ctx: RequestContext):
        self.model = model
        self.ctx = ctx

    def _apply_scope(self, query):
        """Apply tenant_id and workspace_id scope to query.

        Args:
            query: SQLAlchemy query object.

        Returns:
            Query with scope filters applied.
        """
        # Check if model has tenant_id and workspace_id columns
        if hasattr(self.model, "tenant_id") and hasattr(self.model, "workspace_id"):
            return query.where(
                and_(
                    self.model.tenant_id == self.ctx.tenant_id,
                    self.model.workspace_id == self.ctx.workspace_id,
                )
            )
        elif hasattr(self.model, "tenant_id"):
            # Tenant-scoped only
            return query.where(self.model.tenant_id == self.ctx.tenant_id)
        # No scope columns, return as-is (should be rare)
        return query

    def _unwrap_result(self, result: Any | None) -> ModelType | None:
        """Unwrap SQLAlchemy row to model instance.

        Args:
            result: Raw result from SQL execution.

        Returns:
            Model instance or None.
        """
        if result is None:
            return None
        if isinstance(result, self.model):
            return result
        if isinstance(result, list | tuple):
            return result[0] if result else None
        if hasattr(result, "_mapping"):
            return result[0]
        return result

    def _unwrap_all(self, results: list[Any]) -> list[ModelType]:
        """Unwrap list of SQLAlchemy rows to model instances."""
        if not results:
            return []
        if isinstance(results[0], self.model):
            return results
        return [self._unwrap_result(item) for item in results if item is not None]

    def _scoped_by_id_query(self, id: str):
        query = select(self.model).where(self.model.id == id)
        return self._apply_scope(query)

    def _scoped_page_query(self, order_by: str | None, offset: int, limit: int):
        query = select(self.model)
        query = self._apply_scope(query)

        # Apply ordering
        if order_by:
            order_col = getattr(self.model, order_by, None)
            if order_col:
                query = query.order_by(order_col.desc())
        elif hasattr(self.model, "created_at"):
            query = query.order_by(self.model.created_at.desc())

        # Fetch one extra to check has_next
        return query.offset(offset).limit(limit + 1)

    def _scoped_count_query(self):
        query = select(func.count()).select_from(self.model)
        return self._apply_scope(query)

    def _stamp_scope(self, model: ModelType) -> None:
        """Force the request scope onto a model about to be created."""
        if hasattr(model, "tenant_id"):
            model.tenant_id = self.ctx.tenant_id
        if hasattr(model, "workspace_id"):
            model.workspace_id = self.ctx.workspace_id

    def _page(self, results: list[Any], *, offset: int, limit: int) -> PaginatedResponse[ModelType]:
        results = self._unwrap_all(results)
        has_next = len(results) > limit
        items = results[:limit]
        next_offset = offset + limit if has_next else None
        return PaginatedResponse.create(
            items=items,
            page_size=limit,
            has_next=has_next,
            next_offset=next_offset,
        )


class AsyncRepository(_ScopedRepositoryBase[ModelType]):
    """Scope-aware repository on an `AsyncSession`.

    Every query filters by tenant_id and workspace_id from the request
    context; every write stamps the same scope.
    """

    def __init__(self, model: type[ModelType], db: AsyncSession, ctx: RequestContext):
        super().__init__(model, ctx)
        self.db = db

    async def get_by_id(self, id: str) -> ModelType | None:
        """Get model by ID (with scope check)."""
        result = (await self.db.exec(self._scoped_by_id_query(id))).first()
        return self._unwrap_result(result)

    async def get_all(
        self,
        page_token: str | None = None,
        page_size: int = 20,
        order_by: str | None = None,
    ) -> PaginatedResponse[ModelType]:
        """Get all models (paginated, with scope check)."""
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        query = self._scoped_page_query(order_by, offset, limit)
        results = list((await self.db.exec(query)).all())
        return self._page(results, offset=offset, limit=limit)

    async def list(
        self,
        page_token: str | None = None,
        page_size: int = 20,
        order_by: str | None = None,
    ) -> PaginatedResponse[ModelType]:
        """List models (alias for get_all)."""
        return await self.get_all(page_token=page_token, page_size=page_size, order_by=order_by)

    async def create(self, model: ModelType) -> ModelType:
        """Create a new model (with scope enforcement)."""
        self._stamp_scope(model)
        self.db.add(model)
        await self.db.commit()
        await self.db.refresh(model)
        return model

    async def update(self, model: ModelType) -> ModelType:
        """Update an existing model (with scope check)."""
        existing = await self.get_by_id(model.id)
        if not existing:
            raise ValueError(f"{self.model.__name__} not found: {model.id}")

        for key, value in model.model_dump(exclude={"id", "tenant_id", "workspace_id"}).items():
            if hasattr(existing, key):
                setattr(existing, key, value)

        await self.db.commit()
        await self.db.refresh(existing)
        return existing

    async def delete(self, id: str) -> bool:
        """Delete a model by ID (with scope check)."""
        model = await self.get_by_id(id)
        if not model:
            return False

        await self.db.delete(model)
        await self.db.commit()
        return True

    async def count(self) -> int:
        """Count models (with scope check)."""
        return (await self.db.exec(self._scoped_count_query())).one()
