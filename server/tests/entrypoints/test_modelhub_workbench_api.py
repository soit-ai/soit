"""Entrypoint tests for ModelHub workbench APIs."""

from decimal import Decimal

from fastapi import status

from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.modules.modelhub.domain.models import Provider, ProviderModel, SyncJob


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def _seed_modelhub_workbench(db):
    now = utc_now()
    openai_provider = Provider(
        id="prov_workbench_openai",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        slug="openai-main",
        kind="openai",
        name="OpenAI Main",
        credential_secret_id="sec_openai",
        status="active",
        last_healthcheck_at=now,
        created_at=now,
        updated_at=now,
    )
    deepseek_provider = Provider(
        id="prov_workbench_deepseek",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        slug="deepseek-backup",
        kind="deepseek",
        name="DeepSeek Backup",
        credential_secret_id="sec_deepseek",
        status="error",
        last_healthcheck_error="connection failed",
        created_at=now,
        updated_at=now,
    )
    chat_model = ProviderModel(
        id="pmod_workbench_chat",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        provider_id=openai_provider.id,
        provider_kind=openai_provider.kind,
        model_id="gpt-4o-mini",
        display_name="GPT 4o Mini",
        capabilities_json={"model_type": "llm", "capabilities": ["text_generation"]},
        context_window=128000,
        status="active",
        source="platform",
        sync_status="in_sync",
        last_synced_at=now,
        created_at=now,
        updated_at=now,
    )
    embedding_model = ProviderModel(
        id="pmod_workbench_embedding",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        provider_id=openai_provider.id,
        provider_kind=openai_provider.kind,
        model_id="text-embedding-3-small",
        display_name="Text Embedding 3 Small",
        capabilities_json={"model_type": "embedding", "capabilities": ["embedding"]},
        context_window=8192,
        status="active",
        source="platform",
        sync_status="in_sync",
        last_synced_at=now,
        created_at=now,
        updated_at=now,
    )
    disabled_model = ProviderModel(
        id="pmod_workbench_disabled",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        provider_id=deepseek_provider.id,
        provider_kind=deepseek_provider.kind,
        model_id="deepseek-chat",
        display_name="DeepSeek Chat",
        capabilities_json={"model_type": "llm", "capabilities": ["text_generation"]},
        context_window=64000,
        status="disabled",
        source="local",
        sync_status="never_synced",
        created_at=now,
        updated_at=now,
    )
    removed_model = ProviderModel(
        id="pmod_workbench_removed",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        provider_id=openai_provider.id,
        provider_kind=openai_provider.kind,
        model_id="gpt-removed",
        display_name="GPT Removed",
        capabilities_json={"model_type": "llm", "capabilities": ["text_generation"]},
        context_window=32000,
        status="removed",
        source="platform",
        sync_status="user_removed",
        created_at=now,
        updated_at=now,
    )
    success_run = Run(
        id="run_modelhub_workbench_success",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        mode="chat",
        kind="chat",
        subject_kind="thread",
        subject_id="thread_modelhub_success",
        status="succeeded",
        started_at=now,
        ended_at=now,
        duration_ms=200,
    )
    failed_run = Run(
        id="run_modelhub_workbench_failed",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        mode="chat",
        kind="chat",
        subject_kind="thread",
        subject_id="thread_modelhub_failed",
        status="failed",
        error_message="model timeout",
        started_at=now,
        ended_at=now,
        duration_ms=600,
    )
    db.add_all([openai_provider, deepseek_provider, chat_model, embedding_model, disabled_model, removed_model, success_run, failed_run])
    db.flush()
    db.add_all(
        [
            RunCostEntry(
                id="cost_modelhub_chat_prompt",
                run_id=success_run.id,
                tenant_id="test-tenant",
                workspace_id="test-workspace",
                currency="USD",
                amount=Decimal("1.25"),
                unit="tokens",
                quantity=Decimal("300"),
                provider=openai_provider.kind,
                provider_id=openai_provider.id,
                provider_slug=openai_provider.slug,
                provider_kind=openai_provider.kind,
                model_ref=f"model:{openai_provider.slug}:{chat_model.model_id}",
                upstream_model="gpt-4o-mini-2024-07-18",
                prompt_tokens=200,
                completion_tokens=100,
                created_at=now,
            ),
            RunCostEntry(
                id="cost_modelhub_chat_failed",
                run_id=failed_run.id,
                tenant_id="test-tenant",
                workspace_id="test-workspace",
                currency="USD",
                amount=Decimal("0.75"),
                unit="tokens",
                quantity=Decimal("100"),
                provider=openai_provider.kind,
                model_ref=chat_model.model_id,
                prompt_tokens=80,
                completion_tokens=20,
                created_at=now,
            ),
            RunCostEntry(
                id="cost_modelhub_embedding",
                run_id=success_run.id,
                tenant_id="test-tenant",
                workspace_id="test-workspace",
                currency="USD",
                amount=Decimal("0.50"),
                unit="embeddings",
                quantity=Decimal("10"),
                provider=openai_provider.kind,
                provider_id=openai_provider.id,
                provider_slug=openai_provider.slug,
                provider_kind=openai_provider.kind,
                model_ref=f"model:{openai_provider.slug}:{embedding_model.model_id}",
                upstream_model="text-embedding-3-small",
                prompt_tokens=10,
                completion_tokens=0,
                created_at=now,
            ),
            SyncJob(
                id="sync_modelhub_openai",
                tenant_id="test-tenant",
                workspace_id="test-workspace",
                provider_id=openai_provider.id,
                status="succeeded",
                started_at=now,
                ended_at=now,
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    db.commit()
    return {
        "openai_provider": openai_provider,
        "deepseek_provider": deepseek_provider,
        "chat_model": chat_model,
        "embedding_model": embedding_model,
        "disabled_model": disabled_model,
        "removed_model": removed_model,
    }


def test_modelhub_workbench_overview_aggregates_runtime_data(client, db):
    seeded = _seed_modelhub_workbench(db)

    response = client.get("/api/v1/modelhub/workbench/overview", headers=_headers())

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert payload["summary"]["total_models"] == 3
    assert payload["summary"]["available_models"] == 2
    assert payload["summary"]["total_providers"] == 2
    assert payload["summary"]["online_providers"] == 1
    assert payload["summary"]["month_calls"] == 2
    assert payload["summary"]["month_tokens"] == 410
    assert payload["summary"]["month_cost_amount"] == 2.5
    assert payload["summary"]["avg_latency_ms"] == 400
    assert payload["summary"]["abnormal_models"] == 0
    assert payload["model_tabs"]["all"] == 3
    assert payload["model_tabs"]["embedding"] == 1
    assert payload["provider_tabs"]["error"] == 1
    assert payload["trend"]
    assert payload["cost_share"][0]["label"] == "OpenAI Main"
    assert payload["top_models"][0]["id"] == seeded["chat_model"].id
    assert payload["top_models"][0]["month_calls"] == 2
    assert payload["top_providers"][0]["id"] == seeded["openai_provider"].id
    assert payload["quota_reminders"]


def test_modelhub_workbench_models_filters_and_paginates(client, db):
    seeded = _seed_modelhub_workbench(db)

    response = client.get(
        "/api/v1/modelhub/workbench/models?tab=text&keyword=GPT&page_size=1",
        headers=_headers(),
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert payload["tabs"]["all"] == 3
    assert payload["tabs"]["text"] == 2
    assert payload["page_size"] == 1
    assert payload["next_page_token"] is None
    assert [item["id"] for item in payload["items"]] == [seeded["chat_model"].id]
    assert payload["items"][0]["provider_name"] == "OpenAI Main"
    assert payload["items"][0]["provider_slug"] == "openai-main"
    assert payload["items"][0]["status"] == "available"
    assert payload["items"][0]["recent_exception_count"] == 1
    assert payload["items"][0]["today_calls"] == 2
    assert payload["items"][0]["month_cost_amount"] == 2.0
    assert payload["items"][0]["unit_price"] is None

    disabled_response = client.get(
        f"/api/v1/modelhub/workbench/models?provider_id={seeded['deepseek_provider'].id}&status=disabled",
        headers=_headers(),
    )
    assert disabled_response.status_code == status.HTTP_200_OK
    disabled_payload = disabled_response.json()["data"]
    assert [item["id"] for item in disabled_payload["items"]] == [seeded["disabled_model"].id]

    removed_response = client.get(
        "/api/v1/modelhub/workbench/models?status=removed",
        headers=_headers(),
    )
    assert removed_response.status_code == status.HTTP_200_OK
    removed_payload = removed_response.json()["data"]
    assert [item["id"] for item in removed_payload["items"]] == [seeded["removed_model"].id]

    paged_response = client.get("/api/v1/modelhub/workbench/models?page_size=1", headers=_headers())
    assert paged_response.status_code == status.HTTP_200_OK
    assert paged_response.json()["data"]["next_page_token"] is not None


def test_modelhub_workbench_providers_filters_and_empty_costs(client, db):
    seeded = _seed_modelhub_workbench(db)

    response = client.get(
        "/api/v1/modelhub/workbench/providers?tab=online&model_type=embedding&page_size=1",
        headers=_headers(),
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert payload["tabs"]["all"] == 2
    assert payload["tabs"]["online"] == 1
    assert payload["tabs"]["error"] == 1
    assert [item["id"] for item in payload["items"]] == [seeded["openai_provider"].id]
    assert payload["items"][0]["available_models"] == 2
    assert payload["items"][0]["month_calls"] == 2
    assert payload["items"][0]["month_cost_amount"] == 2.5
    assert payload["items"][0]["avg_latency_ms"] == 400
    assert payload["items"][0]["region"] is None
    assert payload["items"][0]["quota_used"] is None

    error_response = client.get("/api/v1/modelhub/workbench/providers?status=error", headers=_headers())
    assert error_response.status_code == status.HTTP_200_OK
    error_payload = error_response.json()["data"]
    assert [item["id"] for item in error_payload["items"]] == [seeded["deepseek_provider"].id]
    assert error_payload["items"][0]["month_calls"] == 0
    assert error_payload["items"][0]["month_cost_amount"] == 0.0
