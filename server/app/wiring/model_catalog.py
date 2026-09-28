"""The model catalog port, served by the model hub."""

from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.catalog import CallableModel
from app.kernel.ports.llm.virtual_models import virtual_model_ref
from app.wiring.services import build_modelhub_service, build_virtual_model_service


class ModelHubCatalog:
    def __init__(self, *, db: AsyncSession, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    async def list_callable_models(self) -> list[CallableModel]:
        models = [
            CallableModel(id=model.model_ref, created_at=model.created_at, owned_by=model.owned_by)
            for model in await build_modelhub_service(db=self.db, ctx=self.ctx).list_runtime_models()
        ]
        models.extend(
            CallableModel(id=virtual_model_ref(model.slug), created_at=model.created_at, owned_by="soit")
            for model in await build_virtual_model_service(db=self.db, ctx=self.ctx).list_virtual_models()
            if model.status == "active"
        )
        return models
