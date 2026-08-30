""" container

Dependency injection container for managing Port instances.
"""

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.events import EventBus
from app.kernel.ports.llm.interface import LLMPort
from app.kernel.ports.plugins.interface import PluginRuntimePort
from app.kernel.ports.secrets.interface import SecretsPort, SecretValueStore
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.ports.tools.interface import ToolPort
from app.kernel.ports.vector.interface import VectorPort
from app.kernel.runtime.runs.writer import TraceWriter
from app.settings.settings import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class IdentityResourceGrantProvider:
    """Identity-backed implementation of kernel resource grant lookup."""

    def allows_resource_action(
        self,
        *,
        ctx: RequestContext,
        resource_type: str,
        resource_id: str,
        action: str,
        effective_action: str,
    ) -> bool:
        from app.infra.db.session import get_db_sync
        from app.modules.identity.infra.repository import ResourceGrantRepository

        db = get_db_sync()
        try:
            grant = ResourceGrantRepository(db, ctx).get_by_resource_user(resource_type, resource_id, ctx.user_id)
            if not grant:
                return False
            allowed_actions = {str(item).strip().lower() for item in (grant.actions or [])}
            return "*" in allowed_actions or action in allowed_actions or effective_action in allowed_actions
        finally:
            db.close()


class IdentityEgressScopePolicyProvider:
    """Identity-backed implementation of scoped egress policies."""

    def get_scope_policy(self, ctx: RequestContext):
        from app.infra.db.session import get_db_sync
        from app.kernel.security.egress import EgressScopePolicy
        from app.modules.identity.infra.repository import (
            TenantRepository,
            WorkspaceRepository,
        )
        from app.modules.security.application.service import SecurityService

        db = get_db_sync()
        try:
            tenant = TenantRepository(db).get_by_id(ctx.tenant_id)
            workspace = WorkspaceRepository(db, ctx).get_by_id(ctx.workspace_id)
            return EgressScopePolicy(
                tenant_allowlist=list((tenant.egress_allowlist if tenant else None) or []),
                tenant_blocklist=list((tenant.egress_blocklist if tenant else None) or []),
                workspace_allowlist=list((workspace.egress_allowlist if workspace else None) or []),
                workspace_blocklist=list((workspace.egress_blocklist if workspace else None) or []),
                # Derived from the same read that produced the rules, so the
                # identifier and the rules cannot disagree about what was live.
                tenant_bundle_id=SecurityService.bundle_id_for(tenant),
                workspace_bundle_id=SecurityService.bundle_id_for(workspace),
            )
        finally:
            db.close()


class ObserveApprovalLedger:
    """Write approval requests and decisions into the governance ledger.

    A run that stops for approval already carries the request in its interrupt
    and its checkpoint, but both are addressed to whoever is watching the
    stream. This writes the same request where it can be found afterwards: from
    the task, from the run, and from the approvals queue.

    It uses its own session on purpose. The run's transaction is mid-flight and
    about to suspend; committing it here to save an approval row would persist
    whatever else that transaction happened to be holding.
    """

    def record_pending(self, ctx: RequestContext, record) -> str | None:
        from app.infra.db.session import get_db_sync
        from app.modules.observe.domain.models import ApprovalRequest
        from app.modules.observe.infra.repository import ApprovalRepository

        db = get_db_sync()
        try:
            approval = ApprovalRepository(db, ctx).create(
                ApprovalRequest(
                    run_id=record.run_id,
                    task_id=record.task_id,
                    thread_id=record.thread_id,
                    agent_id=record.agent_id,
                    title=record.title,
                    policy_ref=record.policy_ref,
                    details_json={
                        **record.details,
                        "tool_call_id": record.tool_call_id,
                    },
                )
            )
            return approval.id
        except Exception:
            logger.warning("Failed to record an approval request", exc_info=True)
            return None
        finally:
            db.close()

    def record_decision(
        self,
        ctx: RequestContext,
        *,
        run_id: str | None,
        tool_call_id: str | None,
        approved: bool,
        decided_by: str | None = None,
    ) -> None:
        from app.infra.db.session import get_db_sync
        from app.kernel.runtime.status import ApprovalStatus
        from app.modules.observe.infra.repository import ApprovalRepository

        if not run_id and not tool_call_id:
            return

        db = get_db_sync()
        try:
            repo = ApprovalRepository(db, ctx)
            pending = repo.list(
                limit=50,
                offset=0,
                status=ApprovalStatus.PENDING.value,
                run_id=run_id,
                task_id=None,
            )
            # One run can be waiting on more than one tool call, so the call is
            # what identifies the request, not the run.
            for approval in pending:
                details = approval.details_json or {}
                if tool_call_id and details.get("tool_call_id") != tool_call_id:
                    continue
                approval.status = (
                    ApprovalStatus.APPROVED.value if approved else ApprovalStatus.REJECTED.value
                )
                approval.resolved_by = decided_by or ctx.user_id
                approval.resolved_at = utc_now()
                repo.update(
                    approval,
                    emit_resolution_event=approval.status,
                )
                break
        except Exception:
            logger.warning("Failed to record an approval decision", exc_info=True)
        finally:
            db.close()


class AuditEgressBlockRecorder:
    """Write refused outbound requests into the audit ledger.

    A refusal is governance evidence, not a metric: it says which subject tried
    to reach which host and why the policy said no. Keeping it in the audit
    ledger means the same query surface answers "how many blocks today" and
    "what exactly was blocked".

    The rows carry no run_id, so they stay out of the run-scoped audit listing
    and cannot drown the per-run evidence a reviewer is reading.
    """

    def record_block(
        self,
        ctx: RequestContext,
        *,
        resource_ref: str,
        url: str | None,
        domain: str | None,
        reason: str,
        bundles: dict[str, str | None] | None = None,
    ) -> None:
        from app.infra.db.session import get_db_sync
        from app.kernel.runtime.db.models.audit import AuditEvent
        from app.kernel.security.egress import EGRESS_BLOCK_EVENT_TYPE

        db = get_db_sync()
        try:
            db.add(
                AuditEvent(
                    tenant_id=ctx.tenant_id,
                    workspace_id=ctx.workspace_id,
                    event_type=EGRESS_BLOCK_EVENT_TYPE,
                    resource_type="egress",
                    resource_id=domain,
                    operation="egress",
                    actor_user_id=ctx.user_id,
                    trace_id=ctx.trace_id,
                    outcome="denied",
                    scope="workspace",
                    payload_json={
                        "resource_ref": resource_ref,
                        "url": url,
                        "domain": domain,
                        "reason": reason,
                        # Which policy said no, so the refusal can be read
                        # again after the policy has moved on.
                        **(bundles or {}),
                    },
                )
            )
            db.commit()
        finally:
            db.close()


class Container:
    """Dependency injection container."""

    def __init__(self):
        """Initialize container."""
        self._singletons: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._setup_defaults()

    def _setup_defaults(self):
        """Setup default factory functions."""
        self._setup_kernel_providers()

        self.register_factory(
            "llm_provider_resolver",
            lambda: self._create_llm_provider_resolver(),
        )

        # LLM Gateway factory
        self.register_factory(
            "llm_port",
            lambda: self._create_llm_port(),
        )

        # Tool Gateway factory
        self.register_factory(
            "tool_port",
            lambda: self._create_tool_port(),
        )

        # Vector Gateway factory
        self.register_factory(
            "vector_port",
            lambda: self._create_vector_port(),
        )

        # Storage Gateway factory
        self.register_factory(
            "storage_port",
            lambda: self._create_storage_port(),
        )

        # Governed HTTP fetch factory
        self.register_factory(
            "http_fetch_port",
            lambda: self._create_http_fetch_port(),
        )

        # Secrets Gateway factory
        self.register_factory(
            "secret_value_store",
            lambda: self._create_secrets_port(),
        )

        # Plugin runtime factory
        self.register_factory(
            "plugin_runtime_port",
            lambda: self._create_plugin_runtime_port(),
        )

        # Event bus factory
        self.register_factory(
            "event_bus",
            lambda: self._create_event_bus(),
        )

    @staticmethod
    def _allows_in_memory_adapters() -> bool:
        """Return whether non-production in-memory adapters are permitted."""
        import os

        if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("SOIT_TESTING") == "1":
            return True
        return (settings.environment or "").strip().lower() in {
            "dev",
            "development",
            "local",
            "test",
            "testing",
        }

    @staticmethod
    def _is_explicit_test_runtime() -> bool:
        """Return whether tests explicitly requested deterministic adapters."""
        import os

        return bool(
            os.getenv("PYTEST_CURRENT_TEST")
            or os.getenv("SOIT_TESTING") == "1"
        )

    def _setup_kernel_providers(self) -> None:
        """Register concrete providers for kernel extension points."""

        from app.kernel.identity.permissions import register_resource_grant_provider
        from app.kernel.security.egress import (
            register_egress_block_recorder,
            register_egress_scope_policy_provider,
        )

        register_resource_grant_provider(IdentityResourceGrantProvider())
        register_egress_scope_policy_provider(IdentityEgressScopePolicyProvider())
        register_egress_block_recorder(AuditEgressBlockRecorder())

    def register_singleton(self, name: str, instance: Any) -> None:
        """Register a singleton instance.

        Args:
            name: Service name.
            instance: Instance to register.
        """
        self._singletons[name] = instance

    def register_factory(self, name: str, factory: Callable[[], Any]) -> None:
        """Register a factory function.

        Args:
            name: Service name.
            factory: Factory function that creates the instance.
        """
        self._factories[name] = factory

    def get(self, name: str) -> Any:
        """Get a service instance.

        Args:
            name: Service name.

        Returns:
            Service instance.

        Raises:
            ValueError: If service not found.
        """
        # Check singletons first
        if name in self._singletons:
            return self._singletons[name]

        # Check factories
        if name in self._factories:
            instance = self._factories[name]()
            # Cache as singleton if not already cached
            if name not in self._singletons:
                self._singletons[name] = instance
            return instance

        raise ValueError(f"Service not found: {name}")

    def get_llm_port(
        self,
        ctx: RequestContext,
        trace_writer: TraceWriter | None = None,
    ) -> LLMPort:
        """Get LLM gateway instance with policy enforcement.

        Args:
            ctx: Request context.
            trace_writer: Optional trace writer for audit.

        Returns:
            LLMPort instance wrapped with policy gateway.
        """
        from app.kernel.ports.llm.policy import LLMPolicyGateway
        from app.modules.billing.application.guard import CreditBalanceGuard

        base_gateway = self.get("llm_port")
        credit_guard = (
            CreditBalanceGuard(db=trace_writer.db, ctx=ctx)
            if trace_writer is not None
            else None
        )
        return LLMPolicyGateway(
            gateway=base_gateway,
            ctx=ctx,
            trace_writer=trace_writer,
            rate_limit_per_minute=ctx.llm_rate_limit_per_minute,
            daily_quota=ctx.llm_daily_quota,
            credit_guard=credit_guard,
            timeout_seconds=settings.llm_timeout_seconds,
            image_timeout_seconds=settings.llm_image_timeout_seconds,
            image_max_retries=settings.llm_image_max_retries,
            content_safety=self.get_content_safety_port(ctx),
            inspect_inbound=settings.content_safety_inspect_inbound,
            inspect_outbound=settings.content_safety_inspect_outbound,
        )

    def get_content_safety_port(self, ctx: RequestContext):
        """Return the content safety provider, or None when inspection is off.

        None means nothing inspects content. Callers must treat that as "no
        such capability" rather than "everything is safe".
        """
        if not settings.content_safety_enabled:
            return None

        if settings.content_safety_provider == "http":
            endpoint = (settings.content_safety_endpoint or "").strip()
            if not endpoint:
                return None

            from app.adapters.safety.http_content_safety import HttpContentSafetyPort

            return HttpContentSafetyPort(
                ctx=ctx,
                endpoint=endpoint,
                timeout_seconds=settings.content_safety_timeout_seconds,
                fail_closed=settings.content_safety_fail_closed,
                api_key=settings.content_safety_api_key,
            )

        from app.kernel.safety.rules import RuleContentSafetyPort, SafetyAction

        def _action(value: str, fallback: SafetyAction) -> SafetyAction:
            try:
                return SafetyAction(value)
            except ValueError:
                # A misspelled action must not silently disable the check.
                logger.warning("Unknown content safety action %r; using %s", value, fallback.value)
                return fallback

        return RuleContentSafetyPort(
            secret_action=_action(settings.content_safety_secret_action, SafetyAction.REDACT),
            pii_action=_action(settings.content_safety_pii_action, SafetyAction.OBSERVE),
        )

    def get_mail_port(self):
        """Return the instance mail adapter, or None when none is configured.

        None means the deployment cannot send mail. Callers must report that
        as unavailable rather than pretending a message went out.
        """
        if not settings.system_mail_enabled:
            return None
        url = (settings.system_mail_url or "").strip()
        if not url:
            return None

        from app.adapters.mail.apprise_mail import AppriseMailPort

        return AppriseMailPort(url)

    def get_tool_port(
        self,
        ctx: RequestContext,
        trace_writer: TraceWriter | None = None,
    ) -> ToolPort:
        """Get Tool gateway instance with policy enforcement.

        Args:
            ctx: Request context.
            trace_writer: Optional trace writer for audit.

        Returns:
            ToolPort instance wrapped with policy gateway.
        """
        from app.kernel.ports.tools.policy import ToolPolicyGateway

        base_gateway = self.get("tool_port")
        base_storage = self.get("storage_port")
        return ToolPolicyGateway(
            gateway=base_gateway,
            ctx=ctx,
            trace_writer=trace_writer,
            storage_port=base_storage,
            secrets_port=self.get_secrets_port(
                ctx,
                db=trace_writer.db if trace_writer is not None else None,
            ),
            rate_limit_per_minute=ctx.tool_rate_limit_per_minute,
            daily_quota=ctx.tool_daily_quota,
        )

    def get_vector_port(
        self,
        ctx: RequestContext,
        trace_writer: TraceWriter | None = None,
    ) -> VectorPort:
        """Get Vector gateway instance with policy enforcement.

        Args:
            ctx: Request context.
            trace_writer: Optional trace writer for audit.

        Returns:
            VectorPort instance wrapped with policy gateway.
        """
        from app.kernel.ports.vector.policy import VectorPolicyGateway

        base_gateway = self.get("vector_port")
        return VectorPolicyGateway(
            gateway=base_gateway,
            ctx=ctx,
            trace_writer=trace_writer,
        )

    def get_storage_port(
        self,
        ctx: RequestContext,
        trace_writer: TraceWriter | None = None,
    ) -> StoragePort:
        """Get Storage gateway instance with policy enforcement.

        Args:
            ctx: Request context.
            trace_writer: Optional trace writer for audit.

        Returns:
            StoragePort instance wrapped with policy gateway.
        """
        from app.kernel.ports.storage.policy import StoragePolicyGateway

        base_gateway = self.get("storage_port")
        return StoragePolicyGateway(
            gateway=base_gateway,
            ctx=ctx,
            trace_writer=trace_writer,
        )

    def get_http_fetch_port(self):
        """Get the governed HTTP fetch gateway."""
        return self.get("http_fetch_port")

    def get_secrets_port(
        self,
        ctx: RequestContext,
        *,
        db=None,
    ) -> SecretsPort:
        """Get Secrets gateway instance with policy enforcement.

        Args:
            ctx: Request context.

        Returns:
            SecretsPort instance wrapped with policy gateway.
        """
        from app.kernel.ports.secrets.policy import SecretsPolicyGateway
        from app.modules.secrets.infra.scoped_port import ScopedSecretsPort

        base_gateway = ScopedSecretsPort(
            ctx=ctx,
            value_store=self.get_secret_value_store(),
            db=db,
        )
        return SecretsPolicyGateway(
            gateway=base_gateway,
            ctx=ctx,
        )

    def get_secret_value_store(self) -> SecretValueStore:
        """Get the trusted low-level secret value store."""
        return self.get("secret_value_store")

    def get_plugin_runtime_port(
        self,
        ctx: RequestContext,
        trace_writer: TraceWriter | None = None,
    ) -> PluginRuntimePort:
        """Get Plugin runtime port with policy enforcement.

        Args:
            ctx: Request context.
            trace_writer: Optional trace writer for audit.

        Returns:
            PluginRuntimePort instance wrapped with policy gateway.
        """
        from app.kernel.ports.plugins.policy import PluginRuntimePolicyGateway

        base_gateway = self.get("plugin_runtime_port")
        base_storage = self.get("storage_port")
        return PluginRuntimePolicyGateway(
            gateway=base_gateway,
            ctx=ctx,
            trace_writer=trace_writer,
            storage_port=base_storage,
        )

    def get_event_bus(self) -> EventBus:
        """Get EventBus instance."""
        return self.get("event_bus")

    def _create_llm_port(self) -> LLMPort:
        """Create LLM gateway instance.

        Returns:
            LLMPort instance.
        """
        import os
        if self._is_explicit_test_runtime():
            from app.adapters.llm.memory import InMemoryLLMPort
            return InMemoryLLMPort()
        providers: dict[str, LLMPort] = {}

        from app.adapters.llm.anthropic import AnthropicLLMPort
        from app.adapters.llm.deepseek import DeepSeekLLMPort
        from app.adapters.llm.openai import OpenAILLMPort
        from app.adapters.llm.router import LLMRouterPort

        openai_api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
        if openai_api_key:
            providers["openai"] = OpenAILLMPort(api_key=openai_api_key)

        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY") or settings.deepseek_api_key
        if deepseek_api_key:
            providers["deepseek"] = DeepSeekLLMPort(
                api_key=deepseek_api_key,
                base_url=os.getenv("DEEPSEEK_BASE_URL") or settings.deepseek_base_url,
            )

        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY") or settings.anthropic_api_key
        if anthropic_api_key:
            providers["anthropic"] = AnthropicLLMPort(
                api_key=anthropic_api_key,
                base_url=os.getenv("ANTHROPIC_BASE_URL") or settings.anthropic_base_url,
            )

        unrouted: set[str] = set()
        if self._allows_in_memory_adapters():
            from app.adapters.llm.memory import InMemoryLLMPort

            providers["test"] = InMemoryLLMPort()
            # The deterministic adapter runs in-process, so no workspace can
            # own a route to it. Without this it would be registered and
            # unreachable, and `model:test:*` refs would fail to resolve.
            unrouted.add("test")
        return LLMRouterPort(
            providers=providers,
            provider_resolver=self.get("llm_provider_resolver"),
            secrets_resolver=lambda ctx: self.get_secrets_port(ctx),
            unrouted_provider_keys=unrouted,
        )

    @staticmethod
    def _create_llm_provider_resolver():
        """Create the shared workspace provider resolver."""
        from app.adapters.llm.provider_resolver import DatabaseProviderResolver

        return DatabaseProviderResolver()

    def _create_tool_port(self) -> ToolPort:
        """Create Tool gateway instance.

        Returns:
            ToolPort instance.
        """
        from app.adapters.tools.router import RegistryToolRouterPort
        plugin_runtime_port = self.get("plugin_runtime_port")
        return RegistryToolRouterPort(
            plugin_runtime_port=plugin_runtime_port,
            secrets_port_factory=lambda ctx: self.get_secrets_port(ctx),
        )

    def _create_vector_port(self) -> VectorPort:
        """Create Vector gateway instance.

        Returns:
            VectorPort instance.
        """
        import os
        if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("SOIT_TESTING") == "1":
            from app.adapters.vector.memory import InMemoryVectorPort
            return InMemoryVectorPort()
        from app.adapters.vector.milvus import MilvusVectorPort
        return MilvusVectorPort()

    def _create_storage_port(self) -> StoragePort:
        """Create Storage gateway instance.

        Returns:
            StoragePort instance.
        """
        import os

        if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("SOIT_TESTING") == "1":
            from app.adapters.storage.memory import InMemoryStoragePort

            return InMemoryStoragePort()

        from app.adapters.storage.fsspec import FsspecStoragePort
        return FsspecStoragePort()

    def _create_http_fetch_port(self):
        """Create the governed HTTP fetch adapter."""
        from app.adapters.http.governed_fetch import GovernedHttpFetchPort

        return GovernedHttpFetchPort()

    def _create_secrets_port(self) -> SecretValueStore:
        """Create the trusted secret value store.

        Returns:
            SecretValueStore instance.
        """
        if self._is_explicit_test_runtime():
            from app.adapters.secrets.memory import InMemorySecretValueStore
            return InMemorySecretValueStore()
        if not settings.vault_url or not settings.vault_token:
            if self._allows_in_memory_adapters():
                from app.adapters.secrets.memory import InMemorySecretValueStore

                return InMemorySecretValueStore()
            raise RuntimeError(
                "Production requires Vault URL and token for the secrets adapter"
            )
        try:
            from app.adapters.secrets.vault import VaultSecretValueStore
        except ModuleNotFoundError as exc:
            if self._allows_in_memory_adapters():
                logger = logging.getLogger(__name__)
                logger.warning(
                    "Vault client is unavailable; using the development in-memory adapter"
                )
                from app.adapters.secrets.memory import InMemorySecretValueStore

                return InMemorySecretValueStore()
            raise RuntimeError("Production Vault client is not installed") from exc
        return VaultSecretValueStore()

    def _create_plugin_runtime_port(self) -> PluginRuntimePort:
        """Create Plugin runtime port instance."""
        from app.adapters.plugins.http_runtime import HTTPPluginRuntimePort

        return HTTPPluginRuntimePort()

    def _create_event_bus(self) -> EventBus:
        """Create event bus instance."""
        from app.kernel.events import InMemoryEventBus, RedisEventBus

        backend = (settings.event_bus_backend or "memory").lower()
        if backend == "redis":
            redis_url = settings.event_bus_redis_url or settings.redis_url
            return RedisEventBus(redis_url=redis_url, channel=settings.event_bus_channel)
        if backend == "memory" and self._allows_in_memory_adapters():
            return InMemoryEventBus()
        if backend == "memory":
            raise RuntimeError(
                "Production requires the Redis event bus backend"
            )
        raise RuntimeError(f"Unsupported event bus backend: {backend}")


# Global container instance
_container: Container | None = None


def get_container() -> Container:
    """Get or create global container instance.

    Returns:
        Container instance.
    """
    global _container
    if _container is None:
        _container = Container()
    return _container


def reset_container() -> None:
    """Reset global container (useful for testing).

    This clears the singleton cache and resets to default factories.
    """
    global _container
    from app.kernel.identity.permissions import reset_resource_grant_provider
    from app.kernel.security.egress import (
        reset_egress_block_recorder,
        reset_egress_scope_policy_provider,
    )

    reset_resource_grant_provider()
    reset_egress_scope_policy_provider()
    reset_egress_block_recorder()
    _container = None
