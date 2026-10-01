"""Knowledge source API: connectors, sources, connection tests and sync runs."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.knowledge.dependencies import get_knowledge_source_service
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.connectors import ConnectionReport, ConnectorDescriptor
from app.modules.knowledge.application.connector_schemas import (
    ConnectionSampleItem,
    ConnectionTestResponse,
    ConnectorFieldOption,
    ConnectorFieldResponse,
    ConnectorResponse,
    EffectiveLimits,
    SourceCreateRequest,
    SourceResponse,
    SourceTestRequest,
    SourceUpdateRequest,
    SyncRunDetailResponse,
    SyncRunResponse,
)
from app.modules.knowledge.application.connector_service import KnowledgeSourceService

router = APIRouter()

ReadCtx = Annotated[RequestContext, Depends(require_workspace_read_ctx)]
WriteCtx = Annotated[RequestContext, Depends(require_workspace_write_ctx)]
SourceService = Annotated[KnowledgeSourceService, Depends(get_knowledge_source_service)]


def _connector_response(descriptor: ConnectorDescriptor) -> ConnectorResponse:
    return ConnectorResponse(
        kind=descriptor.kind,
        label=descriptor.label,
        description=descriptor.description,
        secret=descriptor.secret,
        secret_help=descriptor.secret_help,
        fields=[
            ConnectorFieldResponse(
                key=field.key,
                label=field.label,
                type=field.type,
                required=field.required,
                default=field.default,
                help=field.help,
                placeholder=field.placeholder,
                options=[ConnectorFieldOption(value=o.value, label=o.label) for o in field.options],
                minimum=field.minimum,
                maximum=field.maximum,
            )
            for field in descriptor.fields
        ],
    )


def _source_response(source: Any, active_run_id: str | None) -> SourceResponse:
    limits = KnowledgeSourceService.effective_limits(source)
    return SourceResponse(
        id=source.id,
        tenant_id=source.tenant_id,
        workspace_id=source.workspace_id,
        knowledge_id=source.knowledge_id,
        name=source.name,
        connector_kind=source.connector_kind,
        config=dict(source.config_json or {}),
        secret_id=source.secret_id,
        limits=EffectiveLimits(
            max_items=limits.max_items,
            max_item_bytes=limits.max_item_bytes,
            max_total_bytes=limits.max_total_bytes,
        ),
        schedule_cron=source.schedule_cron,
        schedule_timezone=source.schedule_timezone,
        enabled=source.enabled,
        delete_removed=source.delete_removed,
        next_sync_at=source.next_sync_at,
        last_sync_at=source.last_sync_at,
        last_status=source.last_status,
        last_error=source.last_error,
        last_counts=dict(source.last_counts_json or {}),
        active_run_id=active_run_id,
        created_by=source.created_by,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _report_response(report: ConnectionReport) -> ConnectionTestResponse:
    return ConnectionTestResponse(
        ok=report.ok,
        message=report.message,
        sample=[
            ConnectionSampleItem(
                external_id=item.external_id,
                name=item.name,
                size=item.size,
                modified=item.modified,
                content_type=item.content_type,
            )
            for item in report.sample
        ],
    )


@router.get("/connectors", response_model=list[ConnectorResponse])
async def list_connectors(
    ctx: ReadCtx,
    service: SourceService,
):
    """The connector kinds this deployment offers, with the settings each takes."""

    _ = ctx
    return [_connector_response(descriptor) for descriptor in service.list_connectors()]


@router.get("/{knowledge_id}/sources", response_model=list[SourceResponse])
async def list_sources(
    knowledge_id: str,
    ctx: ReadCtx,
    service: SourceService,
):
    """List a knowledge base's sources."""

    _ = ctx
    return [_source_response(source, active) for source, active in await service.list_sources(knowledge_id)]


@router.post("/{knowledge_id}/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    knowledge_id: str,
    payload: SourceCreateRequest,
    ctx: WriteCtx,
    service: SourceService,
):
    """Create a source."""

    _ = ctx
    return _source_response(await service.create_source(knowledge_id, payload), None)


@router.post("/{knowledge_id}/sources/test", response_model=ConnectionTestResponse)
async def test_draft_source(
    knowledge_id: str,
    payload: SourceTestRequest,
    ctx: WriteCtx,
    service: SourceService,
):
    """Test a connection before it is saved."""

    _ = ctx
    return _report_response(await service.check_draft_connection(knowledge_id, payload))


@router.get("/{knowledge_id}/sources/{source_id}", response_model=SourceResponse)
async def get_source(
    knowledge_id: str,
    source_id: str,
    ctx: ReadCtx,
    service: SourceService,
):
    """Get a source."""

    _ = ctx
    source, active = await service.get_source(knowledge_id, source_id)
    return _source_response(source, active)


@router.patch("/{knowledge_id}/sources/{source_id}", response_model=SourceResponse)
async def update_source(
    knowledge_id: str,
    source_id: str,
    payload: SourceUpdateRequest,
    ctx: WriteCtx,
    service: SourceService,
):
    """Change a source; only the fields sent are changed."""

    _ = ctx
    await service.update_source(knowledge_id, source_id, payload)
    source, active = await service.get_source(knowledge_id, source_id)
    return _source_response(source, active)


@router.delete("/{knowledge_id}/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    knowledge_id: str,
    source_id: str,
    ctx: WriteCtx,
    service: SourceService,
):
    """Delete a source. Documents it already synced stay in the knowledge base."""

    _ = ctx
    await service.delete_source(knowledge_id, source_id)


@router.post("/{knowledge_id}/sources/{source_id}/test", response_model=ConnectionTestResponse)
async def test_source(
    knowledge_id: str,
    source_id: str,
    ctx: WriteCtx,
    service: SourceService,
):
    """Test a saved source's connection and list a sample of what it would sync."""

    _ = ctx
    return _report_response(await service.check_connection(knowledge_id, source_id))


@router.post(
    "/{knowledge_id}/sources/{source_id}/sync",
    response_model=SyncRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def sync_source(
    knowledge_id: str,
    source_id: str,
    ctx: WriteCtx,
    service: SourceService,
):
    """Queue a sync now. A sync already queued or running for the source is a conflict."""

    _ = ctx
    return await service.trigger_sync(knowledge_id, source_id)


@router.get("/{knowledge_id}/sources/{source_id}/runs", response_model=list[SyncRunResponse])
async def list_runs(
    knowledge_id: str,
    source_id: str,
    ctx: ReadCtx,
    service: SourceService,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """A source's sync history, newest first."""

    _ = ctx
    return await service.list_runs(knowledge_id, source_id, limit=limit, offset=offset)


@router.get("/{knowledge_id}/sources/{source_id}/runs/{run_id}", response_model=SyncRunDetailResponse)
async def get_run(
    knowledge_id: str,
    source_id: str,
    run_id: str,
    ctx: ReadCtx,
    service: SourceService,
):
    """One run with its per-item outcomes."""

    _ = ctx
    run = await service.get_run(knowledge_id, source_id, run_id)
    return SyncRunDetailResponse.model_validate(run, from_attributes=True).model_copy(
        update={"outcomes": list(run.outcomes_json or [])}
    )


@router.post("/{knowledge_id}/sources/{source_id}/runs/{run_id}/cancel", response_model=SyncRunResponse)
async def cancel_run(
    knowledge_id: str,
    source_id: str,
    run_id: str,
    ctx: WriteCtx,
    service: SourceService,
):
    """Cancel a queued run, or ask a running one to stop."""

    _ = ctx
    return await service.cancel_run(knowledge_id, source_id, run_id)
