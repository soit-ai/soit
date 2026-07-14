"""Entrypoint tests for ModelHub API."""

from datetime import UTC, datetime

from fastapi import status

from app.kernel.contracts.context import RequestContext
from app.modules.modelhub.application.service import ModelHubService
from app.modules.modelhub.domain.models import Provider, ProviderModel
from app.modules.modelhub.infra.repository import (
    PlatformModelRepository,
    ProviderModelRepository,
    ProviderRepository,
    SyncJobRepository,
)


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


class _TestSecrets:
    async def get_secret(self, *, secret_ref: str) -> str:
        return "test-key"


class _ModelTestCatalog:
    def __init__(self, *, fail_chat: bool = False, fail_embeddings: bool = False):
        self.fail_chat = fail_chat
        self.fail_embeddings = fail_embeddings

    async def healthcheck(self, **kwargs):
        return {"ok": True}

    async def list_models(self, **kwargs):
        return []

    async def test_chat(self, **kwargs):
        if self.fail_chat:
            raise RuntimeError("provider unavailable")
        assert kwargs["api_key"] == "test-key"
        assert kwargs["model_id"] == "gpt-test"
        assert kwargs["input_text"] == "hello"
        return {
            "response": "chat ok",
            "tokens_prompt": 3,
            "tokens_completion": 2,
            "request_id": "chat_req_1",
        }

    async def test_embeddings(self, **kwargs):
        if self.fail_embeddings:
            raise RuntimeError("Embedding test not supported for provider: anthropic")
        assert kwargs["api_key"] == "test-key"
        assert kwargs["model_id"] == "embed-test"
        assert kwargs["input_text"] == "hello"
        return {
            "response": "[0.1,0.2]",
            "tokens_prompt": 4,
            "tokens_completion": 0,
            "request_id": "embed_req_1",
        }


def _modelhub_service(db, ctx: RequestContext, *, catalog=None) -> ModelHubService:
    return ModelHubService(
        db,
        ctx,
        ProviderRepository(db, ctx),
        PlatformModelRepository(db, ctx),
        ProviderModelRepository(db, ctx),
        SyncJobRepository(db, ctx),
        _TestSecrets(),
        catalog or _ModelTestCatalog(),
    )


def test_create_provider_persists_slug_and_configuration_json(client):
    payload = {
        "slug": "deepseek-main",
        "kind": "deepseek",
        "name": "DeepSeek Main",
        "base_url": "https://api.deepseek.com/v1",
        "credential_ref": "secret:deepseek",
        "status": "active",
        "sync_policy_json": {
            "catalog_supported": True,
            "auto_sync": True,
            "interval_minutes": 360,
            "include_models": ["deepseek-chat"],
            "exclude_models": ["*-deprecated"],
            "default_enabled": False,
        },
        "connection_config_json": {
            "api_version": "2026-02-01",
            "timeout_ms": 30000,
            "retry_policy": {"max_retries": 3, "backoff": "exponential"},
            "rate_limit": {"rpm": 1200, "tpm": 240000, "concurrency": 32},
        },
        "auth_config_json": {"auth_type": "bearer"},
        "runtime_config_json": {
            "diagnostics_supported": {"healthcheck": True, "chat": True, "embedding": False},
            "runtime_support": {"chat": True, "stream": True, "embedding": False},
        },
        "governance_config_json": {
            "currency": "USD",
            "pricing_source": "catalog",
            "egress_policy": {"allow_external": True, "allowed_domains": ["api.deepseek.com"]},
            "data_policy": {"files": True, "images": False, "sensitive_data": "confirm"},
            "log_level": "summary",
            "trace_enabled": True,
        },
    }

    response = client.post("/api/v1/modelhub/providers", headers=_headers(), json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()["data"]
    assert data["slug"] == "deepseek-main"
    assert data["connection_config_json"] == payload["connection_config_json"]
    assert data["auth_config_json"] == payload["auth_config_json"]
    assert data["runtime_config_json"] == payload["runtime_config_json"]
    assert data["governance_config_json"] == payload["governance_config_json"]
    assert data["sync_policy_json"]["catalog_supported"] is True


def test_create_openai_compatible_provider_persists_all_configuration_groups(client):
    payload = {
        "slug": "compat-main",
        "kind": "openai_compatible",
        "name": "OpenAI Compatible Main",
        "base_url": "https://llm.example.com/v1",
        "credential_ref": "secret:compat",
        "status": "active",
        "sync_policy_json": {
            "catalog_supported": True,
            "auto_sync": False,
            "interval_minutes": 720,
            "recreate_deleted": True,
            "default_enabled": True,
            "include_models": ["compat-chat"],
            "exclude_models": ["compat-legacy"],
        },
        "connection_config_json": {
            "api_version": "2026-06-01",
            "timeout_ms": 45000,
            "retry_policy": {
                "max_retries": 4,
                "backoff": "exponential",
                "retryable_status_codes": [429, 500, 502, 503],
            },
            "rate_limit": {"rpm": 900, "tpm": 120000, "concurrency": 12},
        },
        "auth_config_json": {"auth_type": "custom_header", "header_name": "X-API-Key"},
        "runtime_config_json": {
            "diagnostics_supported": {"healthcheck": True, "chat": True, "embedding": True},
            "runtime_support": {"chat": True, "stream": True, "embedding": True, "rerank": False},
        },
        "governance_config_json": {
            "currency": "USD",
            "pricing_source": "manual",
            "egress_policy": {"allow_external": True, "allowed_domains": ["llm.example.com"]},
            "data_policy": {"files": True, "images": True, "sensitive_data": "confirm"},
            "log_level": "summary",
            "trace_enabled": True,
        },
    }

    response = client.post("/api/v1/modelhub/providers", headers=_headers(), json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()["data"]
    for key in ("slug", "kind", "name", "base_url", "credential_ref", "status"):
        assert data[key] == payload[key]
    for key in (
        "sync_policy_json",
        "connection_config_json",
        "auth_config_json",
        "runtime_config_json",
        "governance_config_json",
    ):
        assert data[key] == payload[key]


def test_provider_slug_must_be_unique_within_workspace(client):
    payload = {
        "slug": "openai-main",
        "kind": "openai",
        "name": "OpenAI Main",
        "credential_ref": "secret:openai",
        "status": "active",
    }

    first_response = client.post("/api/v1/modelhub/providers", headers=_headers(), json=payload)
    second_response = client.post(
        "/api/v1/modelhub/providers",
        headers=_headers(),
        json={**payload, "name": "OpenAI Backup"},
    )
    assert first_response.status_code == status.HTTP_201_CREATED
    assert second_response.status_code == status.HTTP_400_BAD_REQUEST


def test_provider_slug_lookup_is_workspace_scoped(db):
    first_provider = Provider(
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        slug="openai-main",
        kind="openai",
        name="OpenAI Main",
        credential_ref="secret:openai",
        status="active",
    )
    second_provider = Provider(
        tenant_id="test-tenant",
        workspace_id="other-workspace",
        slug="openai-main",
        kind="openai",
        name="OpenAI Other Workspace",
        credential_ref="secret:openai-other",
        status="active",
    )
    db.add(first_provider)
    db.add(second_provider)
    db.commit()
    db.refresh(first_provider)
    db.refresh(second_provider)

    first_repo = ProviderRepository(
        db,
        RequestContext(
            tenant_id="test-tenant",
            workspace_id="test-workspace",
            user_id="test-user",
            workspace_role="Owner",
        ),
    )
    second_repo = ProviderRepository(
        db,
        RequestContext(
            tenant_id="test-tenant",
            workspace_id="other-workspace",
            user_id="test-user",
            workspace_role="Owner",
        ),
    )

    assert first_repo.get_by_slug("openai-main").id == first_provider.id
    assert second_repo.get_by_slug("openai-main").id == second_provider.id


def test_update_provider_persists_configuration_json(client):
    create_response = client.post(
        "/api/v1/modelhub/providers",
        headers=_headers(),
        json={
            "slug": "openai-main",
            "kind": "openai",
            "name": "OpenAI Main",
            "credential_ref": "secret:openai",
            "status": "active",
        },
    )
    provider_id = create_response.json()["data"]["id"]

    response = client.patch(
        f"/api/v1/modelhub/providers/{provider_id}",
        headers=_headers(),
        json={
            "slug": "openai-production",
            "connection_config_json": {"timeout_ms": 45000},
            "auth_config_json": {"auth_type": "api_key"},
            "runtime_config_json": {"runtime_support": {"chat": True}},
            "governance_config_json": {"trace_enabled": False},
        },
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["slug"] == "openai-production"
    assert data["connection_config_json"] == {"timeout_ms": 45000}
    assert data["auth_config_json"] == {"auth_type": "api_key"}
    assert data["runtime_config_json"] == {"runtime_support": {"chat": True}}
    assert data["governance_config_json"] == {"trace_enabled": False}


def test_update_provider_configuration_preserves_unsubmitted_groups(client):
    create_response = client.post(
        "/api/v1/modelhub/providers",
        headers=_headers(),
        json={
            "slug": "openai-preserve-config",
            "kind": "openai",
            "name": "OpenAI Preserve Config",
            "credential_ref": "secret:openai",
            "status": "active",
            "sync_policy_json": {"auto_sync": True, "include_models": ["gpt-4o-mini"]},
            "connection_config_json": {"timeout_ms": 30000},
            "auth_config_json": {"auth_type": "bearer"},
            "runtime_config_json": {"runtime_support": {"chat": True}},
            "governance_config_json": {"trace_enabled": True},
        },
    )
    provider_id = create_response.json()["data"]["id"]

    response = client.patch(
        f"/api/v1/modelhub/providers/{provider_id}",
        headers=_headers(),
        json={
            "connection_config_json": {"timeout_ms": 60000},
            "governance_config_json": {"trace_enabled": False},
        },
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["sync_policy_json"] == {"auto_sync": True, "include_models": ["gpt-4o-mini"]}
    assert data["connection_config_json"] == {"timeout_ms": 60000}
    assert data["auth_config_json"] == {"auth_type": "bearer"}
    assert data["runtime_config_json"] == {"runtime_support": {"chat": True}}
    assert data["governance_config_json"] == {"trace_enabled": False}


def test_delete_provider_removes_empty_provider_and_missing_provider_returns_error(client):
    create_response = client.post(
        "/api/v1/modelhub/providers",
        headers=_headers(),
        json={
            "slug": "delete-empty-provider",
            "kind": "openai",
            "name": "Delete Empty Provider",
            "credential_ref": "secret:openai",
            "status": "active",
        },
    )
    provider_id = create_response.json()["data"]["id"]

    delete_response = client.delete(f"/api/v1/modelhub/providers/{provider_id}", headers=_headers())
    missing_response = client.delete("/api/v1/modelhub/providers/provider_missing", headers=_headers())

    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert missing_response.status_code == status.HTTP_404_NOT_FOUND


def test_list_providers_returns_latest_model_sync_timestamp(client, db):
    provider = Provider(
        id="prov_sync_timestamp",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        slug="openai-sync-timestamp",
        kind="openai",
        name="OpenAI Sync Timestamp",
        credential_ref="secret:openai",
        status="active",
    )
    older_model = ProviderModel(
        id="pmod_sync_timestamp_old",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        provider_id=provider.id,
        provider_kind=provider.kind,
        model_id="gpt-old",
        status="active",
        source="platform",
        sync_status="in_sync",
        last_synced_at=datetime(2026, 5, 30, 8, 0, tzinfo=UTC),
    )
    newer_model = ProviderModel(
        id="pmod_sync_timestamp_new",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        provider_id=provider.id,
        provider_kind=provider.kind,
        model_id="gpt-new",
        status="active",
        source="platform",
        sync_status="in_sync",
        last_synced_at=datetime(2026, 5, 31, 9, 30, tzinfo=UTC),
    )
    db.add(provider)
    db.add(older_model)
    db.add(newer_model)
    db.commit()

    response = client.get("/api/v1/modelhub/providers", headers=_headers())

    assert response.status_code == status.HTTP_200_OK
    items = response.json()["data"]["items"]
    provider_data = next(item for item in items if item["id"] == provider.id)
    assert provider_data["last_synced_at"].startswith("2026-05-31T09:30:00")


def test_create_provider_model_persists_split_configuration_json(client):
    provider_response = client.post(
        "/api/v1/modelhub/providers",
        headers=_headers(),
        json={
            "slug": "openai-model-config",
            "kind": "openai",
            "name": "OpenAI Model Config",
            "credential_ref": "secret:openai",
            "status": "active",
        },
    )
    provider_id = provider_response.json()["data"]["id"]
    payload = {
        "model_id": "gpt-5.4-mini",
        "display_name": "GPT-5.4 Mini",
        "description": "Configurable model",
        "capabilities_json": {"model_type": "llm", "capabilities": ["chat", "vision"]},
        "architecture_json": {
            "modality": "text+image+file->text",
            "input_modalities": ["text", "image", "file"],
            "output_modalities": ["text"],
            "tokenizer": "GPT",
        },
        "capability_matrix_json": {
            "chat": {
                "catalog": "supported",
                "diagnostics": "passed",
                "runtime": "supported",
                "merged": True,
                "user_override": "auto",
            },
            "reasoning": {
                "catalog": "supported",
                "diagnostics": "failed",
                "runtime": "supported",
                "merged": False,
                "user_override": "enable_after_diagnostics",
            },
        },
        "parameter_config_json": {
            "max_input_files": 20,
            "max_image_count": 10,
            "supported_parameters": ["temperature", "top_p", "tools", "response_format", "reasoning"],
            "default_parameters": {"temperature": 0.7, "top_p": 1, "max_tokens": 4096},
        },
        "pricing_json": {
            "currency": "USD",
            "pricing_source": "catalog",
            "prompt": {"amount": 0.15, "unit": "1M_tokens"},
            "completion": {"amount": 0.6, "unit": "1M_tokens"},
        },
        "diagnostics_json": {
            "last_test_status": "failed",
            "last_test_error": "reasoning.effort rejected by upstream",
            "support": {"catalog": "trusted", "diagnostics": "partial", "runtime": "callable"},
            "runtime_stats": {"month_calls": 12840, "avg_latency_ms": 1749, "error_rate": 0.008},
        },
        "context_window": 128000,
        "max_output_tokens": 16384,
        "lifecycle_status": "stable",
        "raw_meta": {"id": "gpt-5.4-mini"},
        "user_overrides_json": {"fields": ["pricing_json"], "reason": "manual pricing override"},
        "source": "catalog",
        "platform_model_id": "plm_gpt_54_mini",
        "last_synced_at": "2026-06-08T08:00:00Z",
        "status": "active",
    }

    response = client.post(
        f"/api/v1/modelhub/providers/{provider_id}/models",
        headers=_headers(),
        json=payload,
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()["data"]
    assert data["architecture_json"] == payload["architecture_json"]
    assert data["capability_matrix_json"] == payload["capability_matrix_json"]
    assert data["parameter_config_json"] == payload["parameter_config_json"]
    assert data["pricing_json"] == payload["pricing_json"]
    assert data["diagnostics_json"] == payload["diagnostics_json"]
    assert data["user_overrides_json"] == payload["user_overrides_json"]
    assert data["source"] == "catalog"
    assert data["platform_model_id"] == "plm_gpt_54_mini"
    assert data["last_synced_at"].startswith("2026-06-08T08:00:00")


def test_update_provider_model_persists_split_configuration_json_and_marks_overrides(client, db):
    provider = Provider(
        id="prov_model_json_update",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        slug="openai-model-json-update",
        kind="openai",
        name="OpenAI Model JSON Update",
        credential_ref="secret:openai",
        status="active",
    )
    model = ProviderModel(
        id="pmod_model_json_update",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        provider_id=provider.id,
        provider_kind=provider.kind,
        model_id="gpt-5.4-mini",
        display_name="GPT-5.4 Mini",
        status="active",
        source="platform",
        platform_model_id="plm_model_json_update",
        sync_status="in_sync",
    )
    db.add(provider)
    db.add(model)
    db.commit()

    payload = {
        "architecture_json": {"tokenizer": "GPT", "modality": "text->text"},
        "capability_matrix_json": {"chat": {"merged": True, "user_override": "force_on"}},
        "parameter_config_json": {"default_parameters": {"temperature": 0.2}},
        "pricing_json": {"currency": "USD", "completion": {"amount": 0.6, "unit": "1M_tokens"}},
        "diagnostics_json": {"last_test_status": "passed", "override_reason": "manual verification"},
        "user_overrides_json": {"fields": ["pricing_json"], "note": "operator override"},
        "source": "override",
        "platform_model_id": "plm_model_json_update_override",
        "last_synced_at": "2026-06-08T09:30:00Z",
    }

    response = client.patch(
        f"/api/v1/modelhub/providers/{provider.id}/models/{model.id}",
        headers=_headers(),
        json=payload,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["architecture_json"] == payload["architecture_json"]
    assert data["capability_matrix_json"] == payload["capability_matrix_json"]
    assert data["parameter_config_json"] == payload["parameter_config_json"]
    assert data["pricing_json"] == payload["pricing_json"]
    assert data["diagnostics_json"] == payload["diagnostics_json"]
    assert set(data["user_overrides_json"]["fields"]) >= {
        "architecture_json",
        "capability_matrix_json",
        "parameter_config_json",
        "pricing_json",
        "diagnostics_json",
        "user_overrides_json",
    }
    assert data["user_overrides_json"]["note"] == "operator override"
    assert data["source"] == "override"
    assert data["platform_model_id"] == "plm_model_json_update_override"
    assert data["last_synced_at"].startswith("2026-06-08T09:30:00")
    assert data["sync_status"] == "diverged"


def test_update_provider_model_accepts_error_status(client, db):
    provider = Provider(
        id="prov_model_error_status",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        slug="openai-model-error-status",
        kind="openai",
        name="OpenAI Model Error Status",
        credential_ref="secret:openai",
        status="active",
    )
    model = ProviderModel(
        id="pmod_model_error_status",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        provider_id=provider.id,
        provider_kind=provider.kind,
        model_id="gpt-error",
        status="active",
        source="local",
        sync_status="never_synced",
    )
    db.add(provider)
    db.add(model)
    db.commit()

    response = client.patch(
        f"/api/v1/modelhub/providers/{provider.id}/models/{model.id}",
        headers=_headers(),
        json={"status": "error"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["status"] == "error"


def test_provider_model_status_updates_are_visible_in_provider_model_list(client, db):
    provider = Provider(
        id="prov_model_status_updates",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        slug="openai-model-status-updates",
        kind="openai",
        name="OpenAI Model Status Updates",
        credential_ref="secret:openai",
        status="active",
    )
    model = ProviderModel(
        id="pmod_model_status_updates",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        provider_id=provider.id,
        provider_kind=provider.kind,
        model_id="gpt-status",
        status="active",
        source="local",
        sync_status="never_synced",
    )
    db.add(provider)
    db.add(model)
    db.commit()

    disabled_response = client.patch(
        f"/api/v1/modelhub/providers/{provider.id}/models/{model.id}",
        headers=_headers(),
        json={"status": "disabled"},
    )
    disabled_list_response = client.get(
        f"/api/v1/modelhub/providers/{provider.id}/models?status=disabled",
        headers=_headers(),
    )
    active_response = client.patch(
        f"/api/v1/modelhub/providers/{provider.id}/models/{model.id}",
        headers=_headers(),
        json={"status": "active"},
    )

    assert disabled_response.status_code == status.HTTP_200_OK
    assert disabled_response.json()["data"]["status"] == "disabled"
    assert disabled_list_response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in disabled_list_response.json()["data"]["items"]] == [model.id]
    assert active_response.status_code == status.HTTP_200_OK
    assert active_response.json()["data"]["status"] == "active"


def test_modelhub_provider_support_matrix_is_explicit(client, db):
    openai_provider = Provider(
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        kind="openai",
        name="openai-main",
        credential_ref="secret:openai",
        status="active",
    )
    anthropic_provider = Provider(
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        kind="anthropic",
        name="anthropic-catalog-only",
        credential_ref="secret:anthropic",
        status="active",
    )
    db.add(openai_provider)
    db.add(anthropic_provider)
    db.commit()
    db.refresh(openai_provider)
    db.refresh(anthropic_provider)

    response = client.get("/api/v1/modelhub/providers/support-matrix", headers=_headers())

    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    by_kind = {item["provider_kind"]: item for item in data["providers"]}
    assert set(by_kind) == {"openai", "deepseek", "openai_compatible", "anthropic", "gemini"}
    assert by_kind["openai"]["support_status"] == "supported"
    assert by_kind["openai"]["configured"] is True
    assert by_kind["openai"]["configured_provider_ids"] == [openai_provider.id]
    assert by_kind["deepseek"]["support_status"] == "unavailable"
    assert by_kind["openai_compatible"]["support_status"] == "unavailable"
    assert by_kind["anthropic"]["support_status"] == "supported"
    assert by_kind["anthropic"]["configured"] is True
    assert by_kind["anthropic"]["configured_provider_ids"] == [anthropic_provider.id]
    assert by_kind["anthropic"]["chat_supported"] is True
    assert by_kind["anthropic"]["embeddings_supported"] is False
    assert by_kind["anthropic"]["catalog_supported"] is True
    assert by_kind["gemini"]["support_status"] == "unsupported"


def test_delete_platform_provider_model_marks_removed_and_hides_by_default(client, db):
    provider = Provider(
        id="prov_removed_visibility",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        kind="openai",
        name="openai-main",
        credential_ref="secret:openai",
        status="active",
    )
    model = ProviderModel(
        id="pmod_removed_visibility",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        provider_id=provider.id,
        provider_kind=provider.kind,
        model_id="gpt-removed",
        display_name="GPT Removed",
        status="active",
        source="platform",
        platform_model_id="plm_removed_visibility",
        sync_status="in_sync",
    )
    db.add(provider)
    db.add(model)
    db.commit()

    delete_response = client.delete(
        f"/api/v1/modelhub/providers/{provider.id}/models/{model.id}",
        headers=_headers(),
    )
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    refreshed = db.get(ProviderModel, model.id)
    assert refreshed is not None
    assert refreshed.status == "removed"
    assert refreshed.sync_status == "user_removed"

    default_response = client.get(
        f"/api/v1/modelhub/providers/{provider.id}/models",
        headers=_headers(),
    )
    assert default_response.status_code == status.HTTP_200_OK
    assert default_response.json()["data"]["items"] == []

    removed_response = client.get(
        f"/api/v1/modelhub/providers/{provider.id}/models?status=removed",
        headers=_headers(),
    )
    assert removed_response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in removed_response.json()["data"]["items"]] == [model.id]


def test_model_test_endpoints_return_success_and_failure_payloads(client, db, ctx):
    provider = Provider(
        id="prov_model_test",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        slug="model-test-provider",
        kind="openai",
        name="Model Test Provider",
        credential_ref="secret:openai",
        status="active",
    )
    db.add(provider)
    db.commit()

    from app.api.v1.modelhub.dependencies import get_modelhub_service
    from app.main import app

    app.dependency_overrides[get_modelhub_service] = lambda: _modelhub_service(db, ctx)
    try:
        chat_response = client.post(
            "/api/v1/modelhub/test/chat",
            headers=_headers(),
            json={"provider_id": provider.id, "model_id": "gpt-test", "input": "hello"},
        )
        embedding_response = client.post(
            "/api/v1/modelhub/test/embeddings",
            headers=_headers(),
            json={"provider_id": provider.id, "model_id": "embed-test", "input": "hello"},
        )
    finally:
        app.dependency_overrides.pop(get_modelhub_service, None)

    assert chat_response.status_code == status.HTTP_200_OK
    chat = chat_response.json()["data"]
    assert chat["success"] is True
    assert chat["message"] == "ok"
    assert chat["response"] == "chat ok"
    assert chat["tokens_prompt"] == 3
    assert chat["tokens_completion"] == 2
    assert chat["request_id"] == "chat_req_1"
    assert isinstance(chat["latency_ms"], int)

    assert embedding_response.status_code == status.HTTP_200_OK
    embedding = embedding_response.json()["data"]
    assert embedding["success"] is True
    assert embedding["message"] == "ok"
    assert embedding["response"] == "[0.1,0.2]"
    assert embedding["tokens_prompt"] == 4
    assert embedding["tokens_completion"] == 0
    assert embedding["request_id"] == "embed_req_1"

    app.dependency_overrides[get_modelhub_service] = lambda: _modelhub_service(
        db,
        ctx,
        catalog=_ModelTestCatalog(fail_chat=True),
    )
    try:
        failed_response = client.post(
            "/api/v1/modelhub/test/chat",
            headers=_headers(),
            json={"provider_id": provider.id, "model_id": "gpt-test", "input": "hello"},
        )
    finally:
        app.dependency_overrides.pop(get_modelhub_service, None)

    assert failed_response.status_code == status.HTTP_200_OK
    failed = failed_response.json()["data"]
    assert failed["success"] is False
    assert failed["message"] == "provider unavailable"
    assert isinstance(failed["latency_ms"], int)
    assert failed.get("response") is None

    anthropic_provider = Provider(
        id="prov_model_test_anthropic",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        slug="claude-model-test-provider",
        kind="anthropic",
        name="Claude Model Test Provider",
        credential_ref="secret:anthropic",
        status="active",
    )
    db.add(anthropic_provider)
    db.commit()
    app.dependency_overrides[get_modelhub_service] = lambda: _modelhub_service(
        db,
        ctx,
        catalog=_ModelTestCatalog(fail_embeddings=True),
    )
    try:
        unsupported_embedding_response = client.post(
            "/api/v1/modelhub/test/embeddings",
            headers=_headers(),
            json={"provider_id": anthropic_provider.id, "model_id": "claude-sonnet-4-6", "input": "hello"},
        )
    finally:
        app.dependency_overrides.pop(get_modelhub_service, None)

    assert unsupported_embedding_response.status_code == status.HTTP_200_OK
    unsupported_embedding = unsupported_embedding_response.json()["data"]
    assert unsupported_embedding["success"] is False
    assert unsupported_embedding["message"] == "Embedding test not supported for provider: anthropic"
