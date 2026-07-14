"""Provider model removal and sync behavior."""

from __future__ import annotations

import pytest

from app.kernel.commons.errors import KernelError
from app.kernel.contracts.context import RequestContext
from app.modules.modelhub.application.schemas import SyncFromPlatformRequest
from app.modules.modelhub.application.service import ModelHubService
from app.modules.modelhub.domain.models import PlatformModel, Provider, ProviderModel
from app.modules.modelhub.infra.repository import (
    PlatformModelRepository,
    ProviderModelRepository,
    ProviderRepository,
    SyncJobRepository,
)


class _Secrets:
    async def get_secret(self, *, secret_ref: str) -> str:
        return "test-key"


class _Catalog:
    def __init__(self, models=None, error: Exception | None = None):
        self.models = models if models is not None else [{"model_id": "gpt-removed", "display_name": "GPT Removed"}]
        self.error = error

    async def list_models(self, **kwargs):
        if self.error:
            raise self.error
        return self.models


def _service(db, ctx: RequestContext, *, catalog: _Catalog | None = None) -> ModelHubService:
    return ModelHubService(
        db,
        ctx,
        ProviderRepository(db, ctx),
        PlatformModelRepository(db, ctx),
        ProviderModelRepository(db, ctx),
        SyncJobRepository(db, ctx),
        _Secrets(),
        catalog or _Catalog(),
    )


def _seed_removed_platform_model(db, ctx: RequestContext, *, recreate_deleted: bool = False) -> ProviderModel:
    provider = Provider(
        id="prov_removed_sync",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        kind="openai",
        name="OpenAI",
        credential_ref="secret:openai",
        status="active",
        sync_policy_json={"recreate_deleted": recreate_deleted},
    )
    platform = PlatformModel(
        id="plm_removed_sync",
        tenant_id="platform",
        workspace_id="platform",
        provider_kind="openai",
        model_id="gpt-removed",
        display_name="GPT Removed",
        status="active",
    )
    removed = ProviderModel(
        id="pmod_removed_sync",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        provider_id=provider.id,
        provider_kind=provider.kind,
        model_id="gpt-removed",
        display_name="GPT Removed",
        status="removed",
        source="platform",
        platform_model_id=platform.id,
        sync_status="user_removed",
    )
    db.add_all([provider, platform, removed])
    db.commit()
    return removed


@pytest.mark.asyncio
async def test_sync_skips_user_removed_platform_model(db, ctx):
    removed = _seed_removed_platform_model(db, ctx, recreate_deleted=False)
    service = _service(db, ctx)

    job = await service.sync_from_platform("prov_removed_sync")

    refreshed = db.get(ProviderModel, removed.id)
    assert refreshed.status == "removed"
    assert refreshed.sync_status == "user_removed"
    assert job.diff_json["skipped_removed"] == ["gpt-removed"]
    assert "skipped_tombstone" not in job.diff_json


@pytest.mark.asyncio
async def test_sync_recreates_user_removed_model_when_policy_allows(db, ctx):
    removed = _seed_removed_platform_model(db, ctx, recreate_deleted=True)
    service = _service(db, ctx)

    job = await service.sync_from_platform("prov_removed_sync")

    refreshed = db.get(ProviderModel, removed.id)
    assert refreshed.status == "active"
    assert refreshed.sync_status == "in_sync"
    assert job.diff_json["updated"] == ["gpt-removed"]


@pytest.mark.asyncio
async def test_sync_adds_new_platform_model_and_records_diff(db, ctx):
    provider = Provider(
        id="prov_sync_add",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        kind="openai",
        name="OpenAI Add",
        credential_ref="secret:openai",
        status="active",
        sync_policy_json={"default_enabled": True},
    )
    db.add(provider)
    db.commit()
    service = _service(
        db,
        ctx,
        catalog=_Catalog(
            [
                {
                    "model_id": "gpt-new",
                    "display_name": "GPT New",
                    "capabilities_json": {"model_type": "llm"},
                    "context_window": 128000,
                    "max_output_tokens": 4096,
                    "lifecycle_status": "stable",
                    "raw_meta": {"id": "gpt-new"},
                }
            ]
        ),
    )

    job = await service.sync_from_platform(provider.id)

    model = ProviderModelRepository(db, ctx).get_by_provider_and_model_id(provider.id, "gpt-new")
    assert model is not None
    assert model.display_name == "GPT New"
    assert model.status == "active"
    assert model.sync_status == "in_sync"
    assert model.source == "platform"
    assert job.status == "succeeded"
    assert job.diff_json["added"] == ["gpt-new"]


@pytest.mark.asyncio
async def test_sync_anthropic_latest_model_copies_catalog_configuration_json(db, ctx):
    provider = Provider(
        id="prov_sync_anthropic_latest",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        kind="anthropic",
        name="Claude",
        credential_ref="secret:anthropic",
        status="active",
        sync_policy_json={"default_enabled": True},
    )
    db.add(provider)
    db.commit()
    service = _service(
        db,
        ctx,
        catalog=_Catalog(
            [
                {
                    "model_id": "claude-opus-4-8",
                    "display_name": "Claude Opus 4.8",
                    "capabilities_json": {
                        "model_type": "multimodal",
                        "capabilities": ["chat", "vision"],
                    },
                    "context_window": 1_000_000,
                    "max_output_tokens": 128_000,
                    "lifecycle_status": "stable",
                    "raw_meta": {
                        "id": "claude-opus-4-8",
                        "modelhub": {
                            "architecture_json": {
                                "family": "claude",
                                "generation": "4.8",
                                "provider": "anthropic",
                            },
                            "capability_matrix_json": {
                                "chat": True,
                                "vision": True,
                                "embeddings": False,
                            },
                            "parameter_config_json": {
                                "defaults": {"max_tokens": 1024},
                                "limits": {"max_output_tokens": 128_000},
                            },
                            "pricing_json": {
                                "currency": "USD",
                                "unit": "mtok",
                                "input": 5.0,
                                "output": 25.0,
                            },
                            "diagnostics_json": {
                                "test_chat_supported": True,
                                "test_embeddings_supported": False,
                            },
                        },
                    },
                }
            ]
        ),
    )

    job = await service.sync_from_platform(provider.id)

    model = ProviderModelRepository(db, ctx).get_by_provider_and_model_id(
        provider.id,
        "claude-opus-4-8",
    )
    assert model is not None
    assert model.provider_kind == "anthropic"
    assert model.display_name == "Claude Opus 4.8"
    assert model.context_window == 1_000_000
    assert model.max_output_tokens == 128_000
    assert model.architecture_json == {
        "family": "claude",
        "generation": "4.8",
        "provider": "anthropic",
    }
    assert model.capability_matrix_json == {
        "chat": True,
        "vision": True,
        "embeddings": False,
    }
    assert model.parameter_config_json["limits"]["max_output_tokens"] == 128_000
    assert model.pricing_json == {
        "currency": "USD",
        "unit": "mtok",
        "input": 5.0,
        "output": 25.0,
    }
    assert model.diagnostics_json == {
        "test_chat_supported": True,
        "test_embeddings_supported": False,
    }
    assert job.status == "succeeded"
    assert job.diff_json["added"] == ["claude-opus-4-8"]


@pytest.mark.asyncio
async def test_sync_updates_existing_platform_model_and_records_diff(db, ctx):
    provider = Provider(
        id="prov_sync_update",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        kind="openai",
        name="OpenAI Update",
        credential_ref="secret:openai",
        status="active",
    )
    platform = PlatformModel(
        id="plm_sync_update",
        tenant_id="platform",
        workspace_id="platform",
        provider_kind="openai",
        model_id="gpt-update",
        display_name="GPT Update",
        context_window=32000,
        status="active",
    )
    model = ProviderModel(
        id="pmod_sync_update",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        provider_id=provider.id,
        provider_kind=provider.kind,
        model_id="gpt-update",
        display_name="GPT Update",
        context_window=32000,
        status="active",
        source="platform",
        platform_model_id=platform.id,
        sync_status="in_sync",
    )
    db.add_all([provider, platform, model])
    db.commit()
    service = _service(
        db,
        ctx,
        catalog=_Catalog(
            [
                {
                    "model_id": "gpt-update",
                    "display_name": "GPT Update Pro",
                    "context_window": 64000,
                    "max_output_tokens": 8192,
                    "capabilities_json": {"model_type": "llm", "capabilities": ["chat"]},
                }
            ]
        ),
    )

    job = await service.sync_from_platform(provider.id)

    refreshed = db.get(ProviderModel, model.id)
    assert refreshed.display_name == "GPT Update Pro"
    assert refreshed.context_window == 64000
    assert refreshed.max_output_tokens == 8192
    assert refreshed.capabilities_json == {"model_type": "llm", "capabilities": ["chat"]}
    assert refreshed.sync_status == "in_sync"
    assert job.diff_json["updated"] == ["gpt-update"]


@pytest.mark.asyncio
async def test_sync_marks_provider_model_platform_removed_when_catalog_omits_model(db, ctx):
    provider = Provider(
        id="prov_sync_platform_removed",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        kind="openai",
        name="OpenAI Platform Removed",
        credential_ref="secret:openai",
        status="active",
    )
    platform = PlatformModel(
        id="plm_sync_platform_removed",
        tenant_id="platform",
        workspace_id="platform",
        provider_kind="openai",
        model_id="gpt-stale",
        display_name="GPT Stale",
        status="active",
    )
    model = ProviderModel(
        id="pmod_sync_platform_removed",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        provider_id=provider.id,
        provider_kind=provider.kind,
        model_id="gpt-stale",
        display_name="GPT Stale",
        status="active",
        source="platform",
        platform_model_id=platform.id,
        sync_status="in_sync",
    )
    db.add_all([provider, platform, model])
    db.commit()
    service = _service(db, ctx, catalog=_Catalog([]))

    job = await service.sync_from_platform(provider.id)

    refreshed = db.get(ProviderModel, model.id)
    assert refreshed.status == "disabled"
    assert refreshed.sync_status == "platform_removed"
    assert job.diff_json["platform_removed"] == ["gpt-stale"]


@pytest.mark.asyncio
async def test_sync_include_model_ids_limits_provider_model_changes(db, ctx):
    provider = Provider(
        id="prov_sync_include",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        kind="openai",
        name="OpenAI Include",
        credential_ref="secret:openai",
        status="active",
    )
    db.add(provider)
    db.commit()
    service = _service(
        db,
        ctx,
        catalog=_Catalog(
            [
                {"model_id": "gpt-included", "display_name": "GPT Included"},
                {"model_id": "gpt-excluded", "display_name": "GPT Excluded"},
            ]
        ),
    )

    job = await service.sync_from_platform(
        provider.id,
        SyncFromPlatformRequest(include_model_ids=["gpt-included"]),
    )

    repo = ProviderModelRepository(db, ctx)
    included = repo.get_by_provider_and_model_id(provider.id, "gpt-included")
    excluded = repo.get_by_provider_and_model_id(provider.id, "gpt-excluded")
    assert included is not None
    assert excluded is None
    assert job.diff_json["added"] == ["gpt-included"]
    assert "gpt-excluded" not in job.diff_json["added"]


@pytest.mark.asyncio
async def test_sync_failure_records_failed_job_without_mutating_existing_models(db, ctx):
    provider = Provider(
        id="prov_sync_failure",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        kind="openai",
        name="OpenAI Failure",
        credential_ref="secret:openai",
        status="active",
    )
    model = ProviderModel(
        id="pmod_sync_failure",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        provider_id=provider.id,
        provider_kind=provider.kind,
        model_id="gpt-existing",
        display_name="GPT Existing",
        status="active",
        source="platform",
        platform_model_id="plm_sync_failure",
        sync_status="in_sync",
    )
    db.add_all([provider, model])
    db.commit()
    service = _service(db, ctx, catalog=_Catalog(error=RuntimeError("catalog timeout")))

    with pytest.raises(KernelError) as exc_info:
        await service.sync_from_platform(provider.id)

    refreshed = db.get(ProviderModel, model.id)
    jobs = SyncJobRepository(db, ctx).list_by_provider(provider.id)
    assert exc_info.value.code == "MODELHUB_SYNC_FAILED"
    assert exc_info.value.message == "catalog timeout"
    assert refreshed.status == "active"
    assert refreshed.sync_status == "in_sync"
    assert len(jobs) == 1
    assert jobs[0].status == "failed"
    assert jobs[0].error == "catalog timeout"
    assert jobs[0].diff_json == {
        "added": [],
        "updated": [],
        "skipped_override": [],
        "skipped_removed": [],
        "platform_removed": [],
        "unchanged": [],
    }
