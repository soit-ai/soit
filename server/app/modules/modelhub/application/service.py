"""service

ModelHub application service.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import (
    ConflictError,
    KernelError,
    NotFoundError,
    ValidationError,
)
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.pagination import PageToken
from app.kernel.identity.guard import workspace_guard
from app.kernel.ports.llm.interface import ChatMessage, LLMPort
from app.kernel.ports.llm.policy import LLMPolicyGateway
from app.kernel.ports.llm.runtime_config import (
    normalize_capability_matrix,
    resolve_litellm_runtime_config,
)
from app.kernel.ports.secrets.interface import SecretsPort
from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.modules.modelhub.application.ports import ModelReferenceUsagePort
from app.modules.modelhub.application.schemas import (
    ModelTestChatRequest,
    ModelTestEmbeddingRequest,
    ModelWorkbenchCostShareRow,
    ModelWorkbenchModelRow,
    ModelWorkbenchModelsResponse,
    ModelWorkbenchModelTabs,
    ModelWorkbenchOverviewResponse,
    ModelWorkbenchProviderRow,
    ModelWorkbenchProvidersResponse,
    ModelWorkbenchProviderTabs,
    ModelWorkbenchQuotaReminderRow,
    ModelWorkbenchSummary,
    ModelWorkbenchTrendPoint,
    ProviderCreate,
    ProviderModelCreate,
    ProviderModelUpdate,
    ProviderUpdate,
    SyncFromPlatformRequest,
)
from app.modules.modelhub.domain.models import (
    PlatformModel,
    Provider,
    ProviderModel,
    SyncJob,
)
from app.modules.modelhub.infra.providers import ProviderCatalogAdapter
from app.modules.modelhub.infra.repository import (
    PlatformModelRepository,
    ProviderModelRepository,
    ProviderRepository,
    SyncJobRepository,
)


class ModelHubService:
    """ModelHub domain service."""

    PROVIDER_PRESETS: tuple[dict[str, Any], ...] = (
        {
            "provider_kind": "openai",
            "display_name": "OpenAI",
            "default_adapter_backend": "native",
            "supported_adapter_backends": ["native", "litellm"],
            "litellm_provider": "openai",
            "requires_base_url": False,
            "credential_optional": False,
        },
        {
            "provider_kind": "deepseek",
            "display_name": "DeepSeek",
            "default_adapter_backend": "native",
            "supported_adapter_backends": ["native", "litellm"],
            "litellm_provider": "deepseek",
            "requires_base_url": False,
            "credential_optional": False,
        },
        {
            "provider_kind": "anthropic",
            "display_name": "Claude / Anthropic",
            "default_adapter_backend": "native",
            "supported_adapter_backends": ["native", "litellm"],
            "litellm_provider": "anthropic",
            "requires_base_url": False,
            "credential_optional": False,
        },
        {
            "provider_kind": "gemini",
            "display_name": "Gemini",
            "default_adapter_backend": "litellm",
            "supported_adapter_backends": ["litellm"],
            "litellm_provider": "gemini",
            "requires_base_url": False,
            "credential_optional": False,
        },
        {
            "provider_kind": "openai_compatible",
            "display_name": "OpenAI-compatible",
            "default_adapter_backend": "litellm",
            "supported_adapter_backends": ["native", "litellm"],
            "litellm_provider": "openai",
            "requires_base_url": True,
            "credential_optional": False,
        },
        {
            "provider_kind": "azure_openai",
            "display_name": "Azure OpenAI",
            "default_adapter_backend": "litellm",
            "supported_adapter_backends": ["litellm"],
            "litellm_provider": "azure",
            "requires_base_url": True,
            "credential_optional": False,
        },
        {
            "provider_kind": "bedrock",
            "display_name": "Amazon Bedrock",
            "default_adapter_backend": "litellm",
            "supported_adapter_backends": ["litellm"],
            "litellm_provider": "bedrock",
            "requires_base_url": False,
            "credential_optional": True,
        },
        {
            "provider_kind": "openrouter",
            "display_name": "OpenRouter",
            "default_adapter_backend": "litellm",
            "supported_adapter_backends": ["litellm"],
            "litellm_provider": "openrouter",
            "requires_base_url": False,
            "credential_optional": False,
        },
        {
            "provider_kind": "ollama",
            "display_name": "Ollama",
            "default_adapter_backend": "litellm",
            "supported_adapter_backends": ["litellm"],
            "litellm_provider": "ollama_chat",
            "requires_base_url": True,
            "credential_optional": True,
        },
        {
            "provider_kind": "dashscope",
            "display_name": "DashScope",
            "default_adapter_backend": "litellm",
            "supported_adapter_backends": ["litellm"],
            "litellm_provider": "dashscope",
            "requires_base_url": False,
            "credential_optional": False,
        },
    )

    PROVIDER_SUPPORT_MATRIX: tuple[dict[str, Any], ...] = (
        {
            "provider_kind": "openai",
            "display_name": "OpenAI",
            "support_status": "supported",
            "chat_supported": True,
            "embeddings_supported": True,
            "catalog_supported": True,
            "notes": None,
        },
        {
            "provider_kind": "deepseek",
            "display_name": "DeepSeek",
            "support_status": "supported",
            "chat_supported": True,
            "embeddings_supported": False,
            "catalog_supported": False,
            "notes": "Runtime uses the OpenAI-compatible chat adapter; catalog and embeddings diagnostics are not implemented yet.",
        },
        {
            "provider_kind": "openai_compatible",
            "display_name": "OpenAI-compatible",
            "support_status": "supported",
            "chat_supported": True,
            "embeddings_supported": True,
            "catalog_supported": True,
            "notes": "Requires a provider-specific base_url.",
        },
        {
            "provider_kind": "anthropic",
            "display_name": "Claude / Anthropic",
            "support_status": "supported",
            "chat_supported": True,
            "embeddings_supported": False,
            "catalog_supported": True,
            "notes": "Claude catalog, healthcheck, and chat diagnostics are supported; embeddings are not supported by Anthropic.",
        },
        {
            "provider_kind": "gemini",
            "display_name": "Gemini",
            "support_status": "supported",
            "chat_supported": True,
            "embeddings_supported": True,
            "catalog_supported": True,
            "notes": "Runtime is provided through the LiteLLM adapter.",
        },
        {
            "provider_kind": "azure_openai",
            "display_name": "Azure OpenAI",
            "support_status": "supported",
            "chat_supported": True,
            "embeddings_supported": True,
            "catalog_supported": False,
            "notes": "Runtime is provided through the LiteLLM adapter.",
        },
        {
            "provider_kind": "bedrock",
            "display_name": "Amazon Bedrock",
            "support_status": "supported",
            "chat_supported": True,
            "embeddings_supported": True,
            "catalog_supported": False,
            "notes": "Supports explicit AWS secret bindings or ambient IAM credentials.",
        },
        {
            "provider_kind": "openrouter",
            "display_name": "OpenRouter",
            "support_status": "supported",
            "chat_supported": True,
            "embeddings_supported": True,
            "catalog_supported": False,
            "notes": "Runtime is provided through the LiteLLM adapter.",
        },
        {
            "provider_kind": "ollama",
            "display_name": "Ollama",
            "support_status": "supported",
            "chat_supported": True,
            "embeddings_supported": True,
            "catalog_supported": False,
            "notes": "Local runtime can be configured without a credential.",
        },
        {
            "provider_kind": "dashscope",
            "display_name": "DashScope",
            "support_status": "supported",
            "chat_supported": True,
            "embeddings_supported": True,
            "catalog_supported": False,
            "notes": "Runtime is provided through the LiteLLM adapter.",
        },
    )

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        provider_repo: ProviderRepository,
        platform_model_repo: PlatformModelRepository,
        provider_model_repo: ProviderModelRepository,
        sync_job_repo: SyncJobRepository,
        secrets_port: SecretsPort,
        catalog_adapter: ProviderCatalogAdapter,
        litellm_port_factory: Callable[[Provider, dict[str, str]], LLMPort] | None = None,
        provider_cache_invalidator: Callable[..., Awaitable[None]] | None = None,
        runtime_llm_port: LLMPort | None = None,
        model_reference_usage: ModelReferenceUsagePort | None = None,
    ):
        self.db = db
        self.ctx = ctx
        self.provider_repo = provider_repo
        self.platform_model_repo = platform_model_repo
        self.provider_model_repo = provider_model_repo
        self.sync_job_repo = sync_job_repo
        self.secrets_port = secrets_port
        self.catalog_adapter = catalog_adapter
        self.litellm_port_factory = litellm_port_factory
        self.provider_cache_invalidator = provider_cache_invalidator
        self.runtime_llm_port = runtime_llm_port
        self.model_reference_usage = model_reference_usage

    def _build_litellm_port(
        self,
        provider: Provider,
        credentials: dict[str, str],
    ) -> LLMPort:
        if self.litellm_port_factory is None:
            raise ValidationError("LiteLLM adapter is not available in this runtime")
        return self.litellm_port_factory(provider, credentials)

    def _build_litellm_diagnostics_port(
        self,
        provider: Provider,
        credentials: dict[str, str],
    ) -> LLMPort:
        connection = provider.connection_config_json or {}
        retry_policy = connection.get("retry_policy") or {}
        timeout_ms = connection.get("timeout_ms")
        retryable_status_codes = retry_policy.get(
            "retryable_status_codes",
            [408, 409, 429, 500, 502, 503, 504],
        )
        return LLMPolicyGateway(
            self._build_litellm_port(provider, credentials),
            self.ctx,
            trace_writer=None,
            timeout_seconds=float(timeout_ms) / 1000 if timeout_ms is not None else 60.0,
            max_retries=int(retry_policy.get("max_retries", 3)),
            retry_backoff_base_seconds=0.5,
            retry_backoff=str(retry_policy.get("backoff", "exponential")),
            retryable_status_codes=tuple(int(code) for code in retryable_status_codes),
        )

    def _provider_model_ref(self, provider: Provider, model_id: str) -> str:
        return f"model:{provider.slug or provider.kind}:{model_id}"

    async def _invalidate_provider_cache(self, *slugs: str | None) -> None:
        if self.provider_cache_invalidator is None:
            return
        for slug in dict.fromkeys(slug for slug in slugs if slug):
            await self.provider_cache_invalidator(self.ctx, slug)

    async def _invalidate_model_cache(
        self,
        provider: Provider,
        model_id: str,
    ) -> None:
        if self.provider_cache_invalidator is None or not provider.slug:
            return
        await self.provider_cache_invalidator(self.ctx, provider.slug, model_id)

    def _ensure_preset_supports_adapter(
        self,
        provider_kind: str,
        adapter_backend: str,
    ) -> None:
        preset = next(
            (
                item
                for item in self.PROVIDER_PRESETS
                if item["provider_kind"] == provider_kind
            ),
            None,
        )
        if preset and adapter_backend not in preset["supported_adapter_backends"]:
            raise ValidationError(
                f"Provider kind {provider_kind} does not support {adapter_backend} adapter"
            )

    @staticmethod
    def _validate_provider_runtime_configuration(
        *,
        provider_kind: str,
        adapter_backend: str,
        runtime_config: dict[str, Any] | None,
        connection_config: dict[str, Any] | None,
        auth_config: dict[str, Any] | None,
        credential_secret_id: str | None,
    ) -> None:
        if credential_secret_id:
            from app.kernel.ports.secrets.interface import require_opaque_secret_id

            require_opaque_secret_id(credential_secret_id)
        if adapter_backend != "litellm":
            return
        resolve_litellm_runtime_config(
            provider_kind=provider_kind,
            runtime_config=runtime_config,
            connection_config=connection_config,
            auth_config=auth_config,
            credential_secret_id=credential_secret_id,
        )

    @staticmethod
    def normalize_model_status(status: str | None, *, current: str = "active") -> str:
        if status is not None:
            normalized = status.strip().lower()
            if normalized not in {"active", "disabled", "error", "removed"}:
                raise ValidationError(f"Invalid model status: {status}")
            return normalized
        return current

    @staticmethod
    def normalize_lifecycle_status(lifecycle_status: str | None, *, current: str | None = None) -> str | None:
        if lifecycle_status is not None:
            return lifecycle_status
        return current

    @workspace_guard("read")
    async def list_providers(self, limit: int = 200) -> list[Provider]:
        """List providers for workspace."""
        return self.provider_repo.list(limit=limit)

    @workspace_guard("read")
    async def get_provider_last_synced_at(self, provider_id: str):
        """Return the latest catalog sync timestamp for models under a provider."""
        return self.provider_model_repo.latest_synced_at_by_provider(provider_id)

    @workspace_guard("read")
    async def get_provider_support_matrix(self) -> list[dict[str, Any]]:
        """Return explicit provider support and configuration status for this workspace."""
        providers = await self.list_providers(limit=500)
        providers_by_kind: dict[str, list[Provider]] = {}
        for provider in providers:
            kind = provider.kind
            providers_by_kind.setdefault(kind, []).append(provider)

        matrix: list[dict[str, Any]] = []
        for definition in self.PROVIDER_SUPPORT_MATRIX:
            kind = str(definition["provider_kind"])
            configured = [
                provider
                for provider in providers_by_kind.get(kind, [])
                if provider.status in {"active", "error", "disabled"}
            ]
            support_status = str(definition["support_status"])
            if support_status == "supported" and not configured:
                effective_status = "unavailable"
            else:
                effective_status = support_status
            matrix.append(
                {
                    **definition,
                    "support_status": effective_status,
                    "configured": bool(configured),
                    "provider_count": len(configured),
                    "configured_provider_ids": [provider.id for provider in configured],
                }
            )
        return matrix

    async def get_adapter_backend_support(self) -> list[dict[str, Any]]:
        """Return runtime installation status for supported adapter backends."""
        return [
            {
                "adapter_backend": "native",
                "display_name": "Native",
                "available": True,
                "install_hint": None,
            },
            {
                "adapter_backend": "litellm",
                "display_name": "LiteLLM SDK",
                "available": True,
                "install_hint": None,
            },
        ]

    async def get_provider_presets(self) -> list[dict[str, Any]]:
        """Return server-owned provider configuration presets."""
        return [dict(item) for item in self.PROVIDER_PRESETS]

    @workspace_guard("read")
    async def get_workbench_overview(self) -> ModelWorkbenchOverviewResponse:
        """Return ModelHub workbench overview aggregates."""
        providers, model_rows, provider_rows, trend, summary_metrics = self._build_workbench_data(include_removed=True)
        visible_model_rows = [row for row in model_rows if row.status != "removed"]
        summary = self._build_workbench_summary(visible_model_rows, provider_rows, summary_metrics)
        return ModelWorkbenchOverviewResponse(
            summary=summary,
            model_tabs=self._build_model_tabs(visible_model_rows),
            provider_tabs=self._build_provider_tabs(provider_rows),
            trend=trend,
            cost_share=[
                ModelWorkbenchCostShareRow(
                    id=row.id,
                    label=row.name,
                    provider_kind=row.kind,
                    value=row.month_cost_amount,
                    currency=row.currency,
                )
                for row in sorted(provider_rows, key=lambda item: item.month_cost_amount, reverse=True)
                if row.month_cost_amount > 0
            ][:5],
            top_models=sorted(visible_model_rows, key=lambda item: (item.month_calls, item.month_tokens), reverse=True)[:5],
            top_providers=sorted(provider_rows, key=lambda item: (item.month_calls, item.month_tokens), reverse=True)[:5],
            quota_reminders=[
                ModelWorkbenchQuotaReminderRow(
                    id=provider.id,
                    label=provider.name,
                    status="normal" if provider.status == "active" else "warning",
                    quota_used=None,
                    quota_limit=None,
                    quota_percent=None,
                    remaining_quota=None,
                )
                for provider in providers[:5]
            ],
        )

    @workspace_guard("read")
    async def get_workbench_models(
        self,
        *,
        limit: int,
        offset: int,
        tab: str | None = None,
        keyword: str | None = None,
        provider_id: str | None = None,
        status: str | None = None,
        model_type: str | None = None,
    ) -> ModelWorkbenchModelsResponse:
        """Return paginated ModelHub model rows."""
        _, model_rows, provider_rows, _, summary_metrics = self._build_workbench_data(include_removed=True)
        visible_model_rows = [row for row in model_rows if row.status != "removed"]
        filtered_rows = self._filter_model_rows(
            model_rows,
            tab=tab,
            keyword=keyword,
            provider_id=provider_id,
            status=status,
            model_type=model_type,
        )
        visible_rows = filtered_rows[offset: offset + limit]
        has_next = offset + len(visible_rows) < len(filtered_rows)
        next_page_token = PageToken(offset=offset + len(visible_rows), limit=limit).to_string() if has_next else None
        return ModelWorkbenchModelsResponse(
            summary=self._build_workbench_summary(visible_model_rows, provider_rows, summary_metrics),
            tabs=self._build_model_tabs(visible_model_rows),
            items=visible_rows,
            next_page_token=next_page_token,
            page_size=len(visible_rows),
        )

    @workspace_guard("read")
    async def get_workbench_providers(
        self,
        *,
        limit: int,
        offset: int,
        tab: str | None = None,
        keyword: str | None = None,
        status: str | None = None,
        model_type: str | None = None,
    ) -> ModelWorkbenchProvidersResponse:
        """Return paginated ModelHub provider rows."""
        _, model_rows, provider_rows, _, summary_metrics = self._build_workbench_data(include_removed=False)
        filtered_rows = self._filter_provider_rows(
            provider_rows,
            tab=tab,
            keyword=keyword,
            status=status,
            model_type=model_type,
        )
        visible_rows = filtered_rows[offset: offset + limit]
        has_next = offset + len(visible_rows) < len(filtered_rows)
        next_page_token = PageToken(offset=offset + len(visible_rows), limit=limit).to_string() if has_next else None
        return ModelWorkbenchProvidersResponse(
            summary=self._build_workbench_summary(model_rows, provider_rows, summary_metrics),
            tabs=self._build_provider_tabs(provider_rows),
            items=visible_rows,
            next_page_token=next_page_token,
            page_size=len(visible_rows),
        )

    def _build_workbench_data(
        self,
        *,
        include_removed: bool = False,
    ) -> tuple[
        list[Provider],
        list[ModelWorkbenchModelRow],
        list[ModelWorkbenchProviderRow],
        list[ModelWorkbenchTrendPoint],
        dict[str, Any],
    ]:
        providers = self.provider_repo.list(limit=500)
        provider_by_id = {provider.id: provider for provider in providers}
        models = self._list_workbench_provider_models(include_removed=include_removed)
        model_metrics, provider_metrics, summary_metrics, trend = self._build_runtime_metrics(provider_by_id)
        model_rows = [
            self._build_model_row(model, provider_by_id.get(model.provider_id), model_metrics.get(model.id, {}))
            for model in models
            if provider_by_id.get(model.provider_id)
        ]
        provider_rows = [
            self._build_provider_row(
                provider,
                [model for model in models if model.provider_id == provider.id and model.status != "removed"],
                provider_metrics.get(provider.id, {}),
            )
            for provider in providers
        ]
        return providers, model_rows, provider_rows, trend, summary_metrics

    def _list_workbench_provider_models(self, *, include_removed: bool = False) -> list[ProviderModel]:
        clauses = [
            ProviderModel.tenant_id == self.ctx.tenant_id,
            ProviderModel.workspace_id == self.ctx.workspace_id,
        ]
        if not include_removed:
            clauses.append(ProviderModel.status != "removed")
        query = (
            select(ProviderModel)
            .where(and_(*clauses))
            .order_by(desc(ProviderModel.updated_at))
        )
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, ProviderModel) else item[0] for item in results]

    def _build_runtime_metrics(
        self,
        provider_by_id: dict[str, Provider],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any], list[ModelWorkbenchTrendPoint]]:
        month_start, month_end = self._month_window()
        today_start, today_end = self._today_window()
        models = self._list_workbench_provider_models()
        model_by_ref: dict[tuple[str, str], ProviderModel] = {}
        for model in models:
            model_by_ref[(model.provider_id, model.model_id)] = model

        model_metrics: dict[str, dict[str, Any]] = defaultdict(self._empty_metrics)
        provider_metrics: dict[str, dict[str, Any]] = defaultdict(self._empty_metrics)
        daily_metrics: dict[str, dict[str, Any]] = defaultdict(self._empty_metrics)
        summary_metrics = self._empty_metrics()
        query = (
            select(RunCostEntry, Run)
            .join(Run, RunCostEntry.run_id == Run.id)
            .where(
                and_(
                    RunCostEntry.tenant_id == self.ctx.tenant_id,
                    RunCostEntry.workspace_id == self.ctx.workspace_id,
                    Run.tenant_id == self.ctx.tenant_id,
                    Run.workspace_id == self.ctx.workspace_id,
                    RunCostEntry.created_at >= month_start,
                    RunCostEntry.created_at < month_end,
                )
            )
            .order_by(desc(RunCostEntry.created_at))
        )
        for row in self.db.exec(query).all():
            entry = row[0]
            run = row[1]
            provider = self._resolve_entry_provider(entry, provider_by_id)
            model_id = self._entry_model_id(entry.model_ref)
            model = model_by_ref.get((provider.id, model_id)) if provider and model_id else None
            self._accumulate_metrics(summary_metrics, entry, run, today_start, today_end)
            self._accumulate_metrics(provider_metrics[provider.id], entry, run, today_start, today_end) if provider else None
            self._accumulate_metrics(model_metrics[model.id], entry, run, today_start, today_end) if model else None
            day_key = entry.created_at.date().isoformat()
            self._accumulate_metrics(daily_metrics[day_key], entry, run, today_start, today_end)

        trend = [
            ModelWorkbenchTrendPoint(
                date=day,
                calls=len(metrics["run_ids"]),
                tokens=metrics["tokens"],
                cost_amount=round(metrics["amount"], 6),
                avg_latency_ms=self._average_values(metrics["durations"]),
            )
            for day, metrics in sorted(daily_metrics.items())
        ]
        return model_metrics, provider_metrics, summary_metrics, trend

    def _resolve_entry_provider(
        self,
        entry: RunCostEntry,
        provider_by_id: dict[str, Provider],
    ) -> Provider | None:
        if entry.provider_id:
            provider = provider_by_id.get(entry.provider_id)
            if provider is not None:
                return provider
        for provider in provider_by_id.values():
            if entry.provider_slug and entry.provider_slug == provider.slug:
                return provider
            if entry.provider_kind and entry.provider_kind == provider.kind:
                return provider
            if entry.provider and entry.provider in {
                provider.id,
                provider.slug,
                provider.kind,
                provider.name,
            }:
                return provider
        return None

    @staticmethod
    def _entry_model_id(model_ref: str | None) -> str | None:
        if not model_ref:
            return None
        if model_ref.startswith("model:"):
            parts = model_ref.split(":", 2)
            return parts[2] if len(parts) == 3 else None
        return model_ref

    @staticmethod
    def _empty_metrics() -> dict[str, Any]:
        return {
            "run_ids": set(),
            "today_run_ids": set(),
            "tokens": 0,
            "amount": 0.0,
            "currency": None,
            "durations": [],
            "failed_run_ids": set(),
            "last_run_at": None,
        }

    def _accumulate_metrics(
        self,
        metrics: dict[str, Any],
        entry: RunCostEntry,
        run: Run,
        today_start: datetime,
        today_end: datetime,
    ) -> None:
        metrics["run_ids"].add(entry.run_id)
        if today_start <= run.started_at < today_end:
            metrics["today_run_ids"].add(entry.run_id)
        metrics["tokens"] += int(entry.prompt_tokens or 0) + int(entry.completion_tokens or 0)
        metrics["amount"] += float(entry.amount or 0)
        metrics["currency"] = metrics["currency"] or entry.currency
        if run.duration_ms is not None and entry.run_id not in {item[0] for item in metrics["durations"]}:
            metrics["durations"].append((entry.run_id, int(run.duration_ms)))
        if run.status == "failed" or bool(run.error_message):
            metrics["failed_run_ids"].add(entry.run_id)
        last_run_at = metrics["last_run_at"]
        if last_run_at is None or run.started_at > last_run_at:
            metrics["last_run_at"] = run.started_at

    def _build_model_row(
        self,
        model: ProviderModel,
        provider: Provider | None,
        metrics: dict[str, Any],
    ) -> ModelWorkbenchModelRow:
        provider_name = provider.name if provider else model.provider_kind
        status = self._resolve_model_status(model, provider, metrics)
        return ModelWorkbenchModelRow(
            id=model.id,
            provider_id=model.provider_id,
            provider_slug=provider.slug if provider and provider.slug else model.provider_kind,
            provider_name=provider_name,
            provider_kind=model.provider_kind,
            model_id=model.model_id,
            display_name=model.display_name,
            description=model.description,
            model_type=self._model_type(model),
            status=status,
            context_window=model.context_window,
            max_output_tokens=model.max_output_tokens,
            lifecycle_status=model.lifecycle_status,
            sync_status=model.sync_status,
            source=model.source,
            month_calls=len(metrics.get("run_ids", set())),
            today_calls=len(metrics.get("today_run_ids", set())),
            month_tokens=int(metrics.get("tokens", 0)),
            month_cost_amount=round(float(metrics.get("amount", 0)), 6),
            currency=metrics.get("currency"),
            avg_latency_ms=self._average_values(metrics.get("durations", [])),
            recent_exception_count=len(metrics.get("failed_run_ids", set())),
            last_run_at=metrics.get("last_run_at"),
            last_synced_at=model.last_synced_at,
            updated_at=model.updated_at,
            owner=None,
            region=None,
            unit_price=None,
            action_enabled=status == "available",
        )

    def _build_provider_row(
        self,
        provider: Provider,
        models: list[ProviderModel],
        metrics: dict[str, Any],
    ) -> ModelWorkbenchProviderRow:
        sync_times = [model.last_synced_at for model in models if model.last_synced_at]
        return ModelWorkbenchProviderRow(
            id=provider.id,
            name=provider.name,
            kind=provider.kind,
            status=self._provider_workbench_status(provider),
            available_models=sum(1 for model in models if model.status == "active" and model.sync_status != "platform_removed"),
            total_models=len(models),
            model_types=sorted({self._model_type(model) for model in models}),
            month_calls=len(metrics.get("run_ids", set())),
            month_tokens=int(metrics.get("tokens", 0)),
            month_cost_amount=round(float(metrics.get("amount", 0)), 6),
            currency=metrics.get("currency"),
            avg_latency_ms=self._average_values(metrics.get("durations", [])),
            recent_exception_count=len(metrics.get("failed_run_ids", set())),
            availability=None,
            last_sync_at=max(sync_times) if sync_times else None,
            last_healthcheck_at=provider.last_healthcheck_at,
            updated_at=provider.updated_at,
            owner=None,
            region=None,
            quota_used=None,
            quota_limit=None,
            quota_percent=None,
        )

    def _build_workbench_summary(
        self,
        model_rows: list[ModelWorkbenchModelRow],
        provider_rows: list[ModelWorkbenchProviderRow],
        summary_metrics: dict[str, Any],
    ) -> ModelWorkbenchSummary:
        return ModelWorkbenchSummary(
            total_models=len(model_rows),
            available_models=sum(1 for row in model_rows if row.status == "available"),
            total_providers=len(provider_rows),
            online_providers=sum(1 for row in provider_rows if row.status == "online"),
            month_calls=len(summary_metrics.get("run_ids", set())),
            month_tokens=int(summary_metrics.get("tokens", 0)),
            month_cost_amount=round(float(summary_metrics.get("amount", 0)), 6),
            currency=summary_metrics.get("currency"),
            avg_latency_ms=self._average_values(summary_metrics.get("durations", [])),
            abnormal_models=sum(1 for row in model_rows if row.status == "abnormal"),
            updated_at=utc_now(),
        )

    @staticmethod
    def _build_model_tabs(rows: list[ModelWorkbenchModelRow]) -> ModelWorkbenchModelTabs:
        return ModelWorkbenchModelTabs(
            all=len(rows),
            text=sum(1 for row in rows if row.model_type == "llm"),
            embedding=sum(1 for row in rows if row.model_type == "embedding"),
            multimodal=sum(1 for row in rows if row.model_type == "multimodal"),
            rerank=sum(1 for row in rows if row.model_type == "rerank"),
            disabled=sum(1 for row in rows if row.status == "disabled"),
            abnormal=sum(1 for row in rows if row.status == "abnormal"),
        )

    @staticmethod
    def _build_provider_tabs(rows: list[ModelWorkbenchProviderRow]) -> ModelWorkbenchProviderTabs:
        return ModelWorkbenchProviderTabs(
            all=len(rows),
            online=sum(1 for row in rows if row.status == "online"),
            disabled=sum(1 for row in rows if row.status == "disabled"),
            error=sum(1 for row in rows if row.status == "error"),
        )

    def _filter_model_rows(
        self,
        rows: list[ModelWorkbenchModelRow],
        *,
        tab: str | None,
        keyword: str | None,
        provider_id: str | None,
        status: str | None,
        model_type: str | None,
    ) -> list[ModelWorkbenchModelRow]:
        normalized_tab = (tab or "all").strip().lower()
        normalized_keyword = (keyword or "").strip().lower()
        normalized_status = (status or "all").strip().lower()
        normalized_type = (model_type or "all").strip().lower()

        def matches(row: ModelWorkbenchModelRow) -> bool:
            tab_ok = normalized_tab in {"", "all"} or (
                normalized_tab == "text" and row.model_type == "llm"
            ) or row.model_type == normalized_tab or row.status == normalized_tab
            keyword_ok = not normalized_keyword or normalized_keyword in " ".join(
                filter(None, [row.display_name, row.model_id, row.provider_name, row.provider_kind, row.status, row.model_type])
            ).lower()
            provider_ok = not provider_id or provider_id == "all" or row.provider_id == provider_id
            status_ok = (
                row.status != "removed"
                if normalized_status in {"", "all"}
                else row.status == normalized_status
            )
            type_ok = normalized_type in {"", "all"} or row.model_type == normalized_type or (
                normalized_type == "text" and row.model_type == "llm"
            )
            return tab_ok and keyword_ok and provider_ok and status_ok and type_ok

        return [row for row in rows if matches(row)]

    def _filter_provider_rows(
        self,
        rows: list[ModelWorkbenchProviderRow],
        *,
        tab: str | None,
        keyword: str | None,
        status: str | None,
        model_type: str | None,
    ) -> list[ModelWorkbenchProviderRow]:
        normalized_tab = (tab or "all").strip().lower()
        normalized_keyword = (keyword or "").strip().lower()
        normalized_status = (status or "all").strip().lower()
        normalized_type = (model_type or "all").strip().lower()

        def matches(row: ModelWorkbenchProviderRow) -> bool:
            tab_ok = normalized_tab in {"", "all"} or row.status == normalized_tab
            keyword_ok = not normalized_keyword or normalized_keyword in " ".join(
                filter(None, [row.name, row.kind, row.status, " ".join(row.model_types)])
            ).lower()
            status_ok = normalized_status in {"", "all"} or row.status == normalized_status
            type_ok = normalized_type in {"", "all"} or normalized_type in row.model_types or (
                normalized_type == "text" and "llm" in row.model_types
            )
            return tab_ok and keyword_ok and status_ok and type_ok

        return [row for row in rows if matches(row)]

    @staticmethod
    def _model_type(model: ProviderModel) -> str:
        capabilities = model.capabilities_json or {}
        value = str(capabilities.get("model_type") or "").strip().lower()
        if value in {"embedding", "multimodal", "rerank"}:
            return value
        if "embedding" in [str(item).lower() for item in capabilities.get("capabilities", []) if item]:
            return "embedding"
        return "llm"

    @staticmethod
    def _resolve_model_status(
        model: ProviderModel,
        provider: Provider | None,
        metrics: dict[str, Any],
    ) -> str:
        if model.status == "removed":
            return "removed"
        if model.status == "error":
            return "abnormal"
        if model.status != "active" or model.sync_status == "platform_removed":
            return "disabled"
        if provider and provider.status == "error":
            return "abnormal"
        return "available"

    @staticmethod
    def _provider_workbench_status(provider: Provider) -> str:
        if provider.status == "active":
            return "online"
        if provider.status == "error":
            return "error"
        return "disabled"

    @staticmethod
    def _average_values(values: list[Any]) -> int | None:
        numbers = [int(item[1] if isinstance(item, tuple) else item) for item in values if item is not None]
        if not numbers:
            return None
        return int(round(sum(numbers) / len(numbers)))

    @staticmethod
    def _month_window() -> tuple[datetime, datetime]:
        now = utc_now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start.replace(tzinfo=None), end.replace(tzinfo=None)

    @staticmethod
    def _today_window() -> tuple[datetime, datetime]:
        now = utc_now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return start.replace(tzinfo=None), end.replace(tzinfo=None)

    @workspace_guard("write")
    async def create_provider(self, data: ProviderCreate) -> Provider:
        """Create a provider."""
        self._ensure_preset_supports_adapter(data.kind, data.adapter_backend)
        self._validate_provider_runtime_configuration(
            provider_kind=data.kind,
            adapter_backend=data.adapter_backend,
            runtime_config=data.runtime_config_json,
            connection_config=data.connection_config_json,
            auth_config=data.auth_config_json,
            credential_secret_id=data.credential_secret_id,
        )
        if self.provider_repo.get_by_name(data.name):
            raise ValidationError(f"Provider name already exists: {data.name}")
        slug = self._normalize_provider_slug(data.slug or data.kind)
        if self.provider_repo.get_by_slug(slug):
            raise ValidationError(f"Provider slug already exists: {slug}")
        provider = Provider(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            kind=data.kind,
            adapter_backend=data.adapter_backend,
            slug=slug,
            name=data.name,
            base_url=data.base_url,
            credential_secret_id=data.credential_secret_id,
            status=data.status or "active",
            sync_policy_json=data.sync_policy_json,
            connection_config_json=data.connection_config_json,
            auth_config_json=data.auth_config_json,
            runtime_config_json=data.runtime_config_json,
            governance_config_json=data.governance_config_json,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        created = self.provider_repo.create(provider)
        await self._invalidate_provider_cache(created.slug)
        return created

    @workspace_guard("write")
    async def update_provider(self, provider_id: str, data: ProviderUpdate) -> Provider:
        """Update provider."""
        provider = self._get_provider(provider_id)
        self._ensure_preset_supports_adapter(
            data.kind or provider.kind,
            data.adapter_backend or provider.adapter_backend,
        )
        self._validate_provider_runtime_configuration(
            provider_kind=data.kind or provider.kind,
            adapter_backend=data.adapter_backend or provider.adapter_backend,
            runtime_config=(
                data.runtime_config_json
                if data.runtime_config_json is not None
                else provider.runtime_config_json
            ),
            connection_config=(
                data.connection_config_json
                if data.connection_config_json is not None
                else provider.connection_config_json
            ),
            auth_config=(
                data.auth_config_json
                if data.auth_config_json is not None
                else provider.auth_config_json
            ),
            credential_secret_id=(
                data.credential_secret_id
                if data.credential_secret_id is not None
                else provider.credential_secret_id
            ),
        )
        previous_slug = provider.slug
        if data.name and data.name != provider.name:
            existing = self.provider_repo.get_by_name(data.name)
            if existing and existing.id != provider_id:
                raise ValidationError(f"Provider name already exists: {data.name}")
            provider.name = data.name
        if data.slug is not None:
            slug = self._normalize_provider_slug(data.slug)
            existing = self.provider_repo.get_by_slug(slug)
            if existing and existing.id != provider_id:
                raise ValidationError(f"Provider slug already exists: {slug}")
            provider.slug = slug
        if data.kind is not None:
            provider.kind = data.kind
        if data.adapter_backend is not None:
            provider.adapter_backend = data.adapter_backend
        if data.base_url is not None:
            provider.base_url = data.base_url
        if data.credential_secret_id is not None:
            provider.credential_secret_id = data.credential_secret_id
        if data.status is not None:
            provider.status = data.status
        if data.sync_policy_json is not None:
            provider.sync_policy_json = data.sync_policy_json
        if data.connection_config_json is not None:
            provider.connection_config_json = data.connection_config_json
        if data.auth_config_json is not None:
            provider.auth_config_json = data.auth_config_json
        if data.runtime_config_json is not None:
            provider.runtime_config_json = data.runtime_config_json
        if data.governance_config_json is not None:
            provider.governance_config_json = data.governance_config_json
        provider.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(provider)
        await self._invalidate_provider_cache(previous_slug, provider.slug)
        return provider

    @workspace_guard("write")
    async def delete_provider(self, provider_id: str) -> None:
        """Delete provider."""
        provider = self._get_provider(provider_id)
        if self.provider_model_repo.list_by_provider(
            provider_id,
            limit=1,
            include_removed=True,
        ):
            raise ConflictError(
                "Provider cannot be deleted while provider models still exist",
                {"provider_id": provider_id},
            )
        slug = provider.slug
        self.db.delete(provider)
        self.db.commit()
        await self._invalidate_provider_cache(slug)

    @workspace_guard("write")
    async def healthcheck_provider(self, provider_id: str) -> dict[str, Any]:
        """Perform provider healthcheck."""
        provider = self._get_provider(provider_id)
        now = utc_now()
        try:
            if provider.adapter_backend == "litellm":
                credentials = await self._resolve_litellm_credentials(provider)
                models = self.provider_model_repo.list_by_provider(
                    provider.id, limit=1, status="active"
                )
                if not models:
                    raise ValidationError("LiteLLM healthcheck requires an active provider model")
                port = self._build_litellm_diagnostics_port(provider, credentials)
                await port.chat(
                    [ChatMessage(role="user", content="ping")],
                    model=self._provider_model_ref(provider, models[0].model_id),
                    max_tokens=1,
                )
            else:
                api_key = await self._resolve_credential(provider.credential_secret_id)
                await self.catalog_adapter.healthcheck(
                    ctx=self.ctx,
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
            await self._invalidate_provider_cache(provider.slug)
            return {"status": "ok", "message": "healthcheck_ok", "checked_at": now}
        except Exception as exc:
            provider.status = "error"
            provider.last_healthcheck_error = str(exc)
            provider.last_healthcheck_at = now
            provider.updated_at = now
            self.db.commit()
            self.db.refresh(provider)
            await self._invalidate_provider_cache(provider.slug)
            return {"status": "error", "message": str(exc), "checked_at": now}

    @workspace_guard("read")
    async def list_platform_models(self, provider_kind: str, limit: int = 200) -> list[PlatformModel]:
        """List platform models by provider kind."""
        return self.platform_model_repo.list_by_provider_kind(provider_kind, limit=limit)

    @workspace_guard("write")
    async def refresh_platform_models(self, provider_id: str) -> dict[str, Any]:
        """Sync platform models from external provider using provider credentials."""
        provider = self._get_provider(provider_id)
        api_key = await self._resolve_credential(provider.credential_secret_id)
        upstream_models = await self.catalog_adapter.list_models(
            ctx=self.ctx,
            provider_kind=provider.kind,
            api_key=api_key,
            base_url=provider.base_url,
        )
        now = utc_now()
        diff: dict[str, list[str]] = {
            "added": [],
            "updated": [],
            "unchanged": [],
            "disabled": [],
        }
        seen: set[str] = set()
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
                    lifecycle_status=item.get("lifecycle_status"),
                    status="active",
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
                "lifecycle_status",
                "raw_meta",
            ):
                value = item.get(key)
                if value is not None and getattr(existing, key) != value:
                    setattr(existing, key, value)
                    changed = True
            if existing.status != "active":
                existing.status = "active"
                changed = True
            existing.last_seen_at = now
            existing.updated_at = now
            if changed:
                diff["updated"].append(model_id)
            else:
                diff["unchanged"].append(model_id)
        stale_models = self.platform_model_repo.list_by_provider_kind(provider.kind, limit=500)
        for model in stale_models:
            if model.model_id not in seen and model.status == "active":
                model.status = "disabled"
                model.updated_at = now
                diff["disabled"].append(model.model_id)
        self.db.commit()
        return diff

    @workspace_guard("read")
    async def list_provider_models(
        self,
        provider_id: str,
        limit: int = 200,
        *,
        status: str | None = None,
    ) -> list[ProviderModel]:
        """List provider models for a provider."""
        self._get_provider(provider_id)
        normalized_status = self.normalize_model_status(status) if status else None
        models = self.provider_model_repo.list_by_provider(
            provider_id,
            limit=limit,
            status=normalized_status,
        )
        for model in models:
            if model.capability_matrix_json is not None:
                model.capability_matrix_json = normalize_capability_matrix(
                    model.capability_matrix_json
                )
        return models

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
            architecture_json=data.architecture_json,
            capability_matrix_json=(
                normalize_capability_matrix(data.capability_matrix_json)
                if data.capability_matrix_json is not None
                else None
            ),
            parameter_config_json=data.parameter_config_json,
            pricing_json=data.pricing_json,
            diagnostics_json=data.diagnostics_json,
            context_window=data.context_window,
            max_output_tokens=data.max_output_tokens,
            lifecycle_status=self.normalize_lifecycle_status(data.lifecycle_status),
            raw_meta=data.raw_meta,
            status=self.normalize_model_status(data.status),
            source=data.source or "local",
            platform_model_id=data.platform_model_id,
            sync_status="never_synced",
            last_synced_at=data.last_synced_at,
            user_overrides_json=data.user_overrides_json,
            created_at=now,
            updated_at=now,
        )
        created = self.provider_model_repo.create(model)
        await self._invalidate_model_cache(provider, created.model_id)
        return created

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
        original_source = model.source
        overridden_fields = self._collect_override_fields(data)
        if data.display_name is not None:
            model.display_name = data.display_name
        if data.description is not None:
            model.description = data.description
        if data.capabilities_json is not None:
            model.capabilities_json = data.capabilities_json
        if data.config_json is not None:
            model.config_json = data.config_json
        if data.architecture_json is not None:
            model.architecture_json = data.architecture_json
        if data.capability_matrix_json is not None:
            model.capability_matrix_json = normalize_capability_matrix(
                data.capability_matrix_json
            )
        if data.parameter_config_json is not None:
            model.parameter_config_json = data.parameter_config_json
        if data.pricing_json is not None:
            model.pricing_json = data.pricing_json
        if data.diagnostics_json is not None:
            model.diagnostics_json = data.diagnostics_json
        if data.context_window is not None:
            model.context_window = data.context_window
        if data.max_output_tokens is not None:
            model.max_output_tokens = data.max_output_tokens
        lifecycle_status = self.normalize_lifecycle_status(data.lifecycle_status, current=model.lifecycle_status)
        if lifecycle_status is not None:
            model.lifecycle_status = lifecycle_status
        if data.raw_meta is not None:
            model.raw_meta = data.raw_meta
        if data.user_overrides_json is not None:
            model.user_overrides_json = data.user_overrides_json
        if data.source is not None:
            model.source = data.source
        if data.platform_model_id is not None:
            model.platform_model_id = data.platform_model_id
        if data.last_synced_at is not None:
            model.last_synced_at = data.last_synced_at
        model.status = self.normalize_model_status(data.status, current=model.status)
        if original_source == "platform" and overridden_fields:
            model.user_overrides_json = self._merge_overrides(model.user_overrides_json, overridden_fields)
            model.sync_status = "diverged"
        model.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(model)
        await self._invalidate_model_cache(provider, model.model_id)
        return model

    @workspace_guard("write")
    async def delete_provider_model(self, provider_id: str, provider_model_id: str) -> None:
        """Delete provider model."""
        self._get_provider(provider_id)
        model = self.provider_model_repo.get_by_id(provider_model_id)
        if not model or model.provider_id != provider_id:
            raise NotFoundError(f"Provider model not found: {provider_model_id}")
        model_ref = self._provider_model_ref(self._get_provider(provider_id), model.model_id)
        references = (
            self.model_reference_usage.list_references(model_ref)
            if self.model_reference_usage is not None
            else []
        )
        if references:
            raise ConflictError(
                "Provider model cannot be deleted while active configurations reference it",
                {"model_ref": model_ref, "references": references},
            )
        if model.source == "platform" and model.platform_model_id:
            model.status = "removed"
            model.sync_status = "user_removed"
            model.updated_at = utc_now()
            self.db.commit()
            self.db.refresh(model)
            await self._invalidate_model_cache(self._get_provider(provider_id), model.model_id)
            return
        model_id = model.model_id
        self.db.delete(model)
        self.db.commit()
        await self._invalidate_model_cache(self._get_provider(provider_id), model_id)

    @workspace_guard("write")
    async def sync_from_platform(self, provider_id: str, data: SyncFromPlatformRequest | None = None) -> SyncJob:
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
        diff: dict[str, Any] = {
            "added": [],
            "updated": [],
            "skipped_override": [],
            "skipped_removed": [],
            "platform_removed": [],
            "unchanged": [],
        }
        include_ids = set(data.include_model_ids or []) if data else set()
        try:
            await self.refresh_platform_models(provider_id)
            platform_models = self.platform_model_repo.list_by_provider_kind(provider.kind, limit=500)
            existing_models = self.provider_model_repo.list_by_provider(
                provider_id,
                limit=500,
                include_removed=True,
            )
            existing_by_platform_id = {
                item.platform_model_id: item
                for item in existing_models
                if item.platform_model_id
            }
            now = utc_now()
            active_platform_ids: set[str] = set()
            for platform_model in platform_models:
                if include_ids and platform_model.model_id not in include_ids:
                    continue
                if platform_model.status != "active":
                    continue
                active_platform_ids.add(platform_model.id)
                existing = existing_by_platform_id.get(platform_model.id)
                restored_removed = False
                if existing and existing.status == "removed":
                    if not bool((provider.sync_policy_json or {}).get("recreate_deleted")):
                        diff["skipped_removed"].append(platform_model.model_id)
                        continue
                    existing.status = self._default_model_status(provider.sync_policy_json)
                    existing.sync_status = "in_sync"
                    existing.updated_at = now
                    restored_removed = True
                if not existing:
                    projection = self._modelhub_projection_from_platform(platform_model)
                    provider_model = ProviderModel(
                        tenant_id=self.ctx.tenant_id,
                        workspace_id=self.ctx.workspace_id,
                        provider_id=provider_id,
                        provider_kind=provider.kind,
                        model_id=platform_model.model_id,
                        display_name=platform_model.display_name,
                        capabilities_json=platform_model.capabilities_json,
                        architecture_json=projection.get("architecture_json"),
                        capability_matrix_json=projection.get("capability_matrix_json"),
                        parameter_config_json=projection.get("parameter_config_json"),
                        pricing_json=projection.get("pricing_json"),
                        diagnostics_json=projection.get("diagnostics_json"),
                        context_window=platform_model.context_window,
                        max_output_tokens=platform_model.max_output_tokens,
                        lifecycle_status=platform_model.lifecycle_status,
                        raw_meta=platform_model.raw_meta,
                        status=self._default_model_status(provider.sync_policy_json),
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
                if restored_removed or changed == "updated":
                    diff["updated"].append(platform_model.model_id)
                elif changed == "skipped_override":
                    diff["skipped_override"].append(platform_model.model_id)
                else:
                    diff["unchanged"].append(platform_model.model_id)
            if not include_ids:
                for model in existing_models:
                    if model.source != "platform" or not model.platform_model_id:
                        continue
                    if model.status == "removed":
                        continue
                    if model.platform_model_id not in active_platform_ids and model.sync_status != "platform_removed":
                        model.sync_status = "platform_removed"
                        model.status = "disabled"
                        model.updated_at = now
                        diff["platform_removed"].append(model.model_id)
            job.status = "succeeded"
            job.diff_json = diff
            job.ended_at = utc_now()
            job.updated_at = utc_now()
            self.db.commit()
            self.db.refresh(job)
            await self._invalidate_provider_cache(provider.slug)
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
    async def list_sync_jobs(self, provider_id: str, limit: int = 50) -> list[SyncJob]:
        """List sync jobs for provider."""
        self._get_provider(provider_id)
        return self.sync_job_repo.list_by_provider(provider_id, limit=limit)

    @workspace_guard("write")
    async def test_chat(self, data: ModelTestChatRequest) -> dict[str, Any]:
        """Test chat completion for a provider model."""
        provider = self._get_provider(data.provider_id)
        start = utc_now()
        try:
            if self.runtime_llm_port is not None:
                response = await self.runtime_llm_port.chat(
                    [ChatMessage(role="user", content=data.input)],
                    model=self._provider_model_ref(provider, data.model_id),
                )
                result = {
                    "response": response.text,
                    "tokens_prompt": response.tokens_prompt,
                    "tokens_completion": response.tokens_completion,
                    "request_id": None,
                }
            elif provider.adapter_backend == "litellm":
                credentials = await self._resolve_litellm_credentials(provider)
                response = await self._build_litellm_diagnostics_port(provider, credentials).chat(
                    [ChatMessage(role="user", content=data.input)],
                    model=self._provider_model_ref(provider, data.model_id),
                )
                result = {
                    "response": response.text,
                    "tokens_prompt": response.tokens_prompt,
                    "tokens_completion": response.tokens_completion,
                    "request_id": None,
                }
            else:
                api_key = await self._resolve_credential(provider.credential_secret_id)
                result = await self.catalog_adapter.test_chat(
                    ctx=self.ctx,
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
    async def test_embeddings(self, data: ModelTestEmbeddingRequest) -> dict[str, Any]:
        """Test embeddings for a provider model."""
        provider = self._get_provider(data.provider_id)
        start = utc_now()
        try:
            if self.runtime_llm_port is not None:
                response = await self.runtime_llm_port.embed(
                    [data.input],
                    model=self._provider_model_ref(provider, data.model_id),
                )
                result = {
                    "response": str(response.embeddings[0] if response.embeddings else []),
                    "tokens_prompt": response.tokens_used,
                    "tokens_completion": 0,
                    "request_id": None,
                }
            elif provider.adapter_backend == "litellm":
                credentials = await self._resolve_litellm_credentials(provider)
                response = await self._build_litellm_diagnostics_port(provider, credentials).embed(
                    [data.input],
                    model=self._provider_model_ref(provider, data.model_id),
                )
                result = {
                    "response": str(response.embeddings[0] if response.embeddings else []),
                    "tokens_prompt": response.tokens_used,
                    "tokens_completion": 0,
                    "request_id": None,
                }
            else:
                api_key = await self._resolve_credential(provider.credential_secret_id)
                result = await self.catalog_adapter.test_embeddings(
                    ctx=self.ctx,
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

    async def _resolve_credential(self, credential_secret_id: str | None) -> str:
        if not credential_secret_id:
            raise ValidationError("Provider credential_secret_id is required")
        return await self.secrets_port.get_secret(secret_id=credential_secret_id)

    async def _resolve_litellm_credentials(self, provider: Provider) -> dict[str, str]:
        runtime = resolve_litellm_runtime_config(
            provider_kind=provider.kind,
            runtime_config=provider.runtime_config_json,
            connection_config=provider.connection_config_json,
            auth_config=provider.auth_config_json,
            credential_secret_id=provider.credential_secret_id,
        )
        credentials: dict[str, str] = {}
        for parameter, secret_id in runtime.secret_bindings.items():
            credentials[parameter] = await self.secrets_port.get_secret(
                secret_id=secret_id
            )
        return credentials

    def _merge_overrides(self, existing: dict[str, Any] | None, new_fields: set[str]) -> dict[str, Any]:
        payload = existing or {}
        fields = set(payload.get("fields", []) or [])
        fields.update(new_fields)
        payload["fields"] = sorted(fields)
        payload["updated_at"] = utc_now().isoformat()
        return payload

    def _collect_override_fields(self, data: ProviderModelUpdate) -> set[str]:
        fields: set[str] = set()
        for name in (
            "display_name",
            "description",
            "capabilities_json",
            "config_json",
            "architecture_json",
            "capability_matrix_json",
            "parameter_config_json",
            "pricing_json",
            "diagnostics_json",
            "context_window",
            "max_output_tokens",
            "lifecycle_status",
            "raw_meta",
            "user_overrides_json",
            "source",
            "platform_model_id",
            "last_synced_at",
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
        set_field("lifecycle_status", platform.lifecycle_status)
        set_field("raw_meta", platform.raw_meta)
        projection = self._modelhub_projection_from_platform(platform)
        for field in (
            "architecture_json",
            "capability_matrix_json",
            "parameter_config_json",
            "pricing_json",
            "diagnostics_json",
        ):
            value = projection.get(field)
            if value is not None:
                set_field(field, value)
        model.last_synced_at = utc_now()
        if skipped_override:
            model.sync_status = "diverged"
        elif updated:
            model.sync_status = "in_sync"
        model.updated_at = utc_now()
        return "skipped_override" if skipped_override else ("updated" if updated else "unchanged")

    def _default_model_status(self, sync_policy_json: dict[str, Any] | None) -> str:
        if not sync_policy_json:
            return "active"
        return "active" if bool(sync_policy_json.get("default_enabled", True)) else "disabled"

    @staticmethod
    def _modelhub_projection_from_platform(platform: PlatformModel) -> dict[str, Any]:
        raw_meta = platform.raw_meta or {}
        if not isinstance(raw_meta, dict):
            return {}
        projection = raw_meta.get("modelhub") or {}
        if not isinstance(projection, dict):
            return {}
        normalized = dict(projection)
        if normalized.get("capability_matrix_json") is not None:
            normalized["capability_matrix_json"] = normalize_capability_matrix(
                normalized["capability_matrix_json"]
            )
        return normalized

    @staticmethod
    def _normalize_provider_slug(value: str) -> str:
        slug = value.strip()
        if not slug:
            raise ValidationError("Provider slug is required")
        return slug
