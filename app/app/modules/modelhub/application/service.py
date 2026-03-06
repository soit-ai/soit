"""service

ModelHub application service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List, Optional, Set

from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError, ValidationError, KernelError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.guard import workspace_guard
from app.kernel.ports.secrets.interface import SecretsPort
from app.modules.modelhub.domain.models import (
    PlatformModel,
    Provider,
    ProviderModel,
    ProviderModelTombstone,
    SyncJob,
)
from app.modules.modelhub.infra.providers import ProviderCatalogAdapter
from app.modules.modelhub.infra.repository import (
    PlatformModelRepository,
    ProviderRepository,
    ProviderModelRepository,
    ProviderModelTombstoneRepository,
    SyncJobRepository,
)
from app.modules.modelhub.application.schemas import (
    ProviderCreate,
    ProviderUpdate,
    ProviderModelCreate,
    ProviderModelUpdate,
    SyncFromPlatformRequest,
    ModelTestChatRequest,
    ModelTestEmbeddingRequest,
)


class ModelHubService:
    """ModelHub domain service."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        provider_repo: ProviderRepository,
        platform_model_repo: PlatformModelRepository,
        provider_model_repo: ProviderModelRepository,
        tombstone_repo: ProviderModelTombstoneRepository,
        sync_job_repo: SyncJobRepository,
        secrets_port: SecretsPort,
        catalog_adapter: ProviderCatalogAdapter,
    ):
        self.db = db
        self.ctx = ctx
        self.provider_repo = provider_repo
        self.platform_model_repo = platform_model_repo
        self.provider_model_repo = provider_model_repo
        self.tombstone_repo = tombstone_repo
        self.sync_job_repo = sync_job_repo
        self.secrets_port = secrets_port
        self.catalog_adapter = catalog_adapter

    @workspace_guard("read")
    async def list_providers(self, limit: int = 200) -> List[Provider]:
        """List providers for workspace."""
        return self.provider_repo.list(limit=limit)

    @workspace_guard("write")
    async def create_provider(self, data: ProviderCreate) -> Provider:
        """Create a provider."""
        if self.provider_repo.get_by_name(data.name):
            raise ValidationError(f"Provider name already exists: {data.name}")
        provider = Provider(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            kind=data.kind,
            name=data.name,
            base_url=data.base_url,
            credential_ref=data.credential_ref,
            status=data.status or "active",
            sync_policy_json=data.sync_policy_json,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        return self.provider_repo.create(provider)

    @workspace_guard("write")
    async def update_provider(self, provider_id: str, data: ProviderUpdate) -> Provider:
        """Update provider."""
        provider = self._get_provider(provider_id)
        if data.name and data.name != provider.name:
            existing = self.provider_repo.get_by_name(data.name)
            if existing and existing.id != provider_id:
                raise ValidationError(f"Provider name already exists: {data.name}")
            provider.name = data.name
        if data.kind is not None:
            provider.kind = data.kind
        if data.base_url is not None:
            provider.base_url = data.base_url
        if data.credential_ref is not None:
            provider.credential_ref = data.credential_ref
        if data.status is not None:
            provider.status = data.status
        if data.sync_policy_json is not None:
            provider.sync_policy_json = data.sync_policy_json
        provider.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(provider)
        return provider

    @workspace_guard("write")
    async def delete_provider(self, provider_id: str) -> None:
        """Delete provider."""
        provider = self._get_provider(provider_id)
        self.db.delete(provider)
        self.db.commit()

    @workspace_guard("write")
    async def healthcheck_provider(self, provider_id: str) -> Dict[str, Any]:
        """Perform provider healthcheck."""
        provider = self._get_provider(provider_id)
        api_key = await self._resolve_credential(provider.credential_ref)
        now = utc_now()
        try:
            await self.catalog_adapter.healthcheck(
                provider_kind=provider.kind,
                api_key=api_key,
                base_url=provider.base_url,
            )
            provider.status = "active"
            provider.last_healthcheck_error = None
            provider.last_healthcheck_at = now
            provider.updated_at = now
            self.db.commit()
            self.db.refresh(provider)
            return {"status": "ok", "message": "healthcheck_ok", "checked_at": now}
        except Exception as exc:
            provider.status = "error"
            provider.last_healthcheck_error = str(exc)
            provider.last_healthcheck_at = now
            provider.updated_at = now
            self.db.commit()
            self.db.refresh(provider)
            return {"status": "error", "message": str(exc), "checked_at": now}

    @workspace_guard("read")
    async def list_platform_models(self, provider_kind: str, limit: int = 200) -> List[PlatformModel]:
        """List platform models by provider kind."""
        return self.platform_model_repo.list_by_provider_kind(provider_kind, limit=limit)

    @workspace_guard("write")
    async def refresh_platform_models(self, provider_id: str) -> Dict[str, Any]:
        """Sync platform models from external provider using provider credentials."""
        provider = self._get_provider(provider_id)
        api_key = await self._resolve_credential(provider.credential_ref)
        upstream_models = await self.catalog_adapter.list_models(
            provider_kind=provider.kind,
            api_key=api_key,
            base_url=provider.base_url,
        )
        now = utc_now()
        diff = {"added": [], "updated": [], "unchanged": [], "disabled": []}
        seen: Set[str] = set()
        for item in upstream_models:
            model_id = item.get("model_id")
            if not model_id:
                continue
            seen.add(model_id)
            existing = self.platform_model_repo.get_by_kind_and_model_id(provider.kind, model_id)
            if not existing:
                platform_model = PlatformModel(
                    tenant_id="platform",
                    workspace_id="platform",
                    provider_kind=provider.kind,
                    model_id=model_id,
                    display_name=item.get("display_name"),
                    raw_meta=item.get("raw_meta"),
                    capabilities_json=item.get("capabilities_json"),
                    context_window=item.get("context_window"),
                    max_output_tokens=item.get("max_output_tokens"),
                    lifecycle=item.get("lifecycle"),
                    is_active=True,
                    last_seen_at=now,
                    created_at=now,
                    updated_at=now,
                )
                self.platform_model_repo.create(platform_model)
                diff["added"].append(model_id)
                continue
            changed = False
            for key in (
                "display_name",
                "capabilities_json",
                "context_window",
                "max_output_tokens",
                "lifecycle",
                "raw_meta",
            ):
                value = item.get(key)
                if value is not None and getattr(existing, key) != value:
                    setattr(existing, key, value)
                    changed = True
            if existing.is_active is False:
                existing.is_active = True
                changed = True
            existing.last_seen_at = now
            existing.updated_at = now
            if changed:
                diff["updated"].append(model_id)
            else:
                diff["unchanged"].append(model_id)
        if seen:
            stale_models = self.platform_model_repo.list_by_provider_kind(provider.kind, limit=500)
            for model in stale_models:
                if model.model_id not in seen and model.is_active:
                    model.is_active = False
                    model.updated_at = now
                    diff["disabled"].append(model.model_id)
        self.db.commit()
        return diff

    @workspace_guard("read")
    async def list_provider_models(self, provider_id: str, limit: int = 200) -> List[ProviderModel]:
        """List provider models for a provider."""
        self._get_provider(provider_id)
        return self.provider_model_repo.list_by_provider(provider_id, limit=limit)

    @workspace_guard("write")
    async def create_provider_model(self, provider_id: str, data: ProviderModelCreate) -> ProviderModel:
        """Create a local provider model."""
        provider = self._get_provider(provider_id)
        if self.provider_model_repo.get_by_provider_and_model_id(provider_id, data.model_id):
            raise ValidationError(f"Model already exists for provider: {data.model_id}")
        now = utc_now()
        model = ProviderModel(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            provider_id=provider_id,
            provider_kind=provider.kind,
            model_id=data.model_id,
            display_name=data.display_name,
            description=data.description,
            capabilities_json=data.capabilities_json,
            config_json=data.config_json,
            context_window=data.context_window,
            max_output_tokens=data.max_output_tokens,
            lifecycle=data.lifecycle,
            raw_meta=data.raw_meta,
            enabled=data.enabled,
            source="local",
            sync_status="never_synced",
            created_at=now,
            updated_at=now,
        )
        return self.provider_model_repo.create(model)

    @workspace_guard("write")
    async def update_provider_model(
        self,
        provider_id: str,
        provider_model_id: str,
        data: ProviderModelUpdate,
    ) -> ProviderModel:
        """Update provider model."""
        provider = self._get_provider(provider_id)
        model = self.provider_model_repo.get_by_id(provider_model_id)
        if not model or model.provider_id != provider.id:
            raise NotFoundError(f"Provider model not found: {provider_model_id}")
        overridden_fields = self._collect_override_fields(data)
        if data.display_name is not None:
            model.display_name = data.display_name
        if data.description is not None:
            model.description = data.description
        if data.capabilities_json is not None:
            model.capabilities_json = data.capabilities_json
        if data.config_json is not None:
            model.config_json = data.config_json
        if data.context_window is not None:
            model.context_window = data.context_window
        if data.max_output_tokens is not None:
            model.max_output_tokens = data.max_output_tokens
        if data.lifecycle is not None:
            model.lifecycle = data.lifecycle
        if data.raw_meta is not None:
            model.raw_meta = data.raw_meta
        if data.enabled is not None:
            model.enabled = data.enabled
        if model.source == "platform" and overridden_fields:
            model.user_overrides_json = self._merge_overrides(model.user_overrides_json, overridden_fields)
            model.sync_status = "diverged"
        model.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(model)
        return model

    @workspace_guard("write")
    async def delete_provider_model(self, provider_id: str, provider_model_id: str) -> None:
        """Delete provider model."""
        self._get_provider(provider_id)
        model = self.provider_model_repo.get_by_id(provider_model_id)
        if not model or model.provider_id != provider_id:
            raise NotFoundError(f"Provider model not found: {provider_model_id}")
        if model.source == "platform" and model.platform_model_id:
            tombstone = ProviderModelTombstone(
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                provider_id=provider_id,
                platform_model_id=model.platform_model_id,
                deleted_at=utc_now(),
            )
            self.tombstone_repo.create(tombstone)
        self.db.delete(model)
        self.db.commit()

    @workspace_guard("write")
    async def sync_from_platform(self, provider_id: str, data: Optional[SyncFromPlatformRequest] = None) -> SyncJob:
        """Sync provider models from platform catalog."""
        provider = self._get_provider(provider_id)
        job = SyncJob(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            provider_id=provider_id,
            status="running",
            started_at=utc_now(),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        job = self.sync_job_repo.create(job)
        diff: Dict[str, Any] = {
            "added": [],
            "updated": [],
            "skipped_override": [],
            "skipped_tombstone": [],
            "platform_removed": [],
            "unchanged": [],
        }
        include_ids = set(data.include_model_ids or []) if data else set()
        try:
            await self.refresh_platform_models(provider_id)
            platform_models = self.platform_model_repo.list_by_provider_kind(provider.kind, limit=500)
            existing_models = self.provider_model_repo.list_by_provider(provider_id, limit=500)
            existing_by_platform_id = {
                item.platform_model_id: item
                for item in existing_models
                if item.platform_model_id
            }
            now = utc_now()
            active_platform_ids: Set[str] = set()
            for platform_model in platform_models:
                if include_ids and platform_model.model_id not in include_ids:
                    continue
                if not platform_model.is_active:
                    continue
                active_platform_ids.add(platform_model.id)
                if self._is_tombstoned(provider_id, platform_model.id, provider.sync_policy_json):
                    diff["skipped_tombstone"].append(platform_model.model_id)
                    continue
                existing = existing_by_platform_id.get(platform_model.id)
                if not existing:
                    provider_model = ProviderModel(
                        tenant_id=self.ctx.tenant_id,
                        workspace_id=self.ctx.workspace_id,
                        provider_id=provider_id,
                        provider_kind=provider.kind,
                        model_id=platform_model.model_id,
                        display_name=platform_model.display_name,
                        capabilities_json=platform_model.capabilities_json,
                        context_window=platform_model.context_window,
                        max_output_tokens=platform_model.max_output_tokens,
                        lifecycle=platform_model.lifecycle,
                        raw_meta=platform_model.raw_meta,
                        enabled=self._default_enabled(provider.sync_policy_json),
                        source="platform",
                        platform_model_id=platform_model.id,
                        sync_status="in_sync",
                        last_synced_at=now,
                        created_at=now,
                        updated_at=now,
                    )
                    self.provider_model_repo.create(provider_model)
                    diff["added"].append(platform_model.model_id)
                    continue
                changed = self._sync_provider_model(existing, platform_model)
                if changed == "updated":
                    diff["updated"].append(platform_model.model_id)
                elif changed == "skipped_override":
                    diff["skipped_override"].append(platform_model.model_id)
                else:
                    diff["unchanged"].append(platform_model.model_id)
            if not include_ids:
                for model in existing_models:
                    if model.source != "platform" or not model.platform_model_id:
                        continue
                    if model.platform_model_id not in active_platform_ids and model.sync_status != "platform_removed":
                        model.sync_status = "platform_removed"
                        model.enabled = False
                        model.updated_at = now
                        diff["platform_removed"].append(model.model_id)
            job.status = "succeeded"
            job.diff_json = diff
            job.ended_at = utc_now()
            job.updated_at = utc_now()
            self.db.commit()
            self.db.refresh(job)
            return job
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            job.diff_json = diff
            job.ended_at = utc_now()
            job.updated_at = utc_now()
            self.db.commit()
            self.db.refresh(job)
            raise KernelError("MODELHUB_SYNC_FAILED", str(exc))

    @workspace_guard("read")
    async def list_sync_jobs(self, provider_id: str, limit: int = 50) -> List[SyncJob]:
        """List sync jobs for provider."""
        self._get_provider(provider_id)
        return self.sync_job_repo.list_by_provider(provider_id, limit=limit)

    @workspace_guard("write")
    async def test_chat(self, data: ModelTestChatRequest) -> Dict[str, Any]:
        """Test chat completion for a provider model."""
        provider = self._get_provider(data.provider_id)
        api_key = await self._resolve_credential(provider.credential_ref)
        start = utc_now()
        try:
            result = await self.catalog_adapter.test_chat(
                provider_kind=provider.kind,
                api_key=api_key,
                base_url=provider.base_url,
                model_id=data.model_id,
                input_text=data.input,
            )
            elapsed = int((utc_now() - start).total_seconds() * 1000)
            return {
                "success": True,
                "message": "ok",
                "response": result.get("response"),
                "latency_ms": elapsed,
                "tokens_prompt": result.get("tokens_prompt"),
                "tokens_completion": result.get("tokens_completion"),
                "request_id": result.get("request_id"),
            }
        except Exception as exc:
            elapsed = int((utc_now() - start).total_seconds() * 1000)
            return {
                "success": False,
                "message": str(exc),
                "latency_ms": elapsed,
            }

    @workspace_guard("write")
    async def test_embeddings(self, data: ModelTestEmbeddingRequest) -> Dict[str, Any]:
        """Test embeddings for a provider model."""
        provider = self._get_provider(data.provider_id)
        api_key = await self._resolve_credential(provider.credential_ref)
        start = utc_now()
        try:
            result = await self.catalog_adapter.test_embeddings(
                provider_kind=provider.kind,
                api_key=api_key,
                base_url=provider.base_url,
                model_id=data.model_id,
                input_text=data.input,
            )
            elapsed = int((utc_now() - start).total_seconds() * 1000)
            return {
                "success": True,
                "message": "ok",
                "response": result.get("response"),
                "latency_ms": elapsed,
                "tokens_prompt": result.get("tokens_prompt"),
                "tokens_completion": result.get("tokens_completion"),
                "request_id": result.get("request_id"),
            }
        except Exception as exc:
            elapsed = int((utc_now() - start).total_seconds() * 1000)
            return {
                "success": False,
                "message": str(exc),
                "latency_ms": elapsed,
            }

    def _get_provider(self, provider_id: str) -> Provider:
        provider = self.provider_repo.get_by_id(provider_id)
        if not provider:
            raise NotFoundError(f"Provider not found: {provider_id}")
        return provider

    async def _resolve_credential(self, credential_ref: Optional[str]) -> str:
        if not credential_ref:
            raise ValidationError("Provider credential_ref is required")
        secret_ref = credential_ref
        if credential_ref.startswith("sec_"):
            secret_ref = f"secret:{credential_ref}"
        if not credential_ref.startswith("secret:") and credential_ref.startswith("sec_") is False:
            secret_ref = credential_ref
        return await self.secrets_port.get_secret(secret_ref=secret_ref)

    def _merge_overrides(self, existing: Optional[Dict[str, Any]], new_fields: Set[str]) -> Dict[str, Any]:
        payload = existing or {}
        fields = set(payload.get("fields", []) or [])
        fields.update(new_fields)
        payload["fields"] = sorted(fields)
        payload["updated_at"] = utc_now().isoformat()
        return payload

    def _collect_override_fields(self, data: ProviderModelUpdate) -> Set[str]:
        fields: Set[str] = set()
        for name in (
            "display_name",
            "description",
            "capabilities_json",
            "context_window",
            "max_output_tokens",
            "lifecycle",
            "raw_meta",
        ):
            if getattr(data, name) is not None:
                fields.add(name)
        return fields

    def _sync_provider_model(self, model: ProviderModel, platform: PlatformModel) -> str:
        overrides = set((model.user_overrides_json or {}).get("fields", []) or [])
        updated = False
        skipped_override = False
        def set_field(field: str, value: Any):
            nonlocal updated, skipped_override
            if field in overrides:
                skipped_override = True
                return
            if getattr(model, field) != value:
                setattr(model, field, value)
                updated = True
        set_field("display_name", platform.display_name)
        set_field("capabilities_json", platform.capabilities_json)
        set_field("context_window", platform.context_window)
        set_field("max_output_tokens", platform.max_output_tokens)
        set_field("lifecycle", platform.lifecycle)
        set_field("raw_meta", platform.raw_meta)
        model.last_synced_at = utc_now()
        if skipped_override:
            model.sync_status = "diverged"
        elif updated:
            model.sync_status = "in_sync"
        model.updated_at = utc_now()
        return "skipped_override" if skipped_override else ("updated" if updated else "unchanged")

    def _is_tombstoned(
        self,
        provider_id: str,
        platform_model_id: str,
        sync_policy_json: Optional[Dict[str, Any]],
    ) -> bool:
        recreate = bool((sync_policy_json or {}).get("recreate_deleted"))
        if recreate:
            return False
        return self.tombstone_repo.exists(provider_id, platform_model_id)

    def _default_enabled(self, sync_policy_json: Optional[Dict[str, Any]]) -> bool:
        if not sync_policy_json:
            return True
        return bool(sync_policy_json.get("default_enabled", True))
