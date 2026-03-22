""" container

Dependency injection container for managing Port instances.
"""

from typing import Optional, Dict, Any, TypeVar, Type, Callable
from functools import lru_cache
import logging

from app.kernel.ports.llm.interface import LLMPort
from app.kernel.ports.tools.interface import ToolPort
from app.kernel.ports.vector.interface import VectorPort
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.ports.secrets.interface import SecretsPort
from app.kernel.ports.plugins.interface import PluginRuntimePort
from app.kernel.contracts.context import RequestContext
from app.kernel.trace.writer import TraceWriter
from app.settings.settings import settings
from app.kernel.events import EventBus


T = TypeVar("T")


class Container:
    """Dependency injection container."""
    
    def __init__(self):
        """Initialize container."""
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._setup_defaults()
    
    def _setup_defaults(self):
        """Setup default factory functions."""
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
        
        # Secrets Gateway factory
        self.register_factory(
            "secrets_port",
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
        trace_writer: Optional[TraceWriter] = None,
    ) -> LLMPort:
        """Get LLM gateway instance with policy enforcement.
        
        Args:
            ctx: Request context.
            trace_writer: Optional trace writer for audit.
            
        Returns:
            LLMPort instance wrapped with policy gateway.
        """
        from app.kernel.ports.llm.policy import LLMPolicyGateway
        
        base_gateway = self.get("llm_port")
        return LLMPolicyGateway(
            gateway=base_gateway,
            ctx=ctx,
            trace_writer=trace_writer,
            rate_limit_per_minute=ctx.llm_rate_limit_per_minute,
            daily_quota=ctx.llm_daily_quota,
        )
    
    def get_tool_port(
        self,
        ctx: RequestContext,
        trace_writer: Optional[TraceWriter] = None,
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
            secrets_port=self.get_secrets_port(ctx),
            rate_limit_per_minute=ctx.tool_rate_limit_per_minute,
            daily_quota=ctx.tool_daily_quota,
        )
    
    def get_vector_port(
        self,
        ctx: RequestContext,
        trace_writer: Optional[TraceWriter] = None,
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
        trace_writer: Optional[TraceWriter] = None,
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
    
    def get_secrets_port(
        self,
        ctx: RequestContext,
    ) -> SecretsPort:
        """Get Secrets gateway instance with policy enforcement.
        
        Args:
            ctx: Request context.
            
        Returns:
            SecretsPort instance wrapped with policy gateway.
        """
        from app.kernel.ports.secrets.policy import SecretsPolicyGateway
        
        base_gateway = self.get("secrets_port")
        return SecretsPolicyGateway(
            gateway=base_gateway,
            ctx=ctx,
        )

    def get_plugin_runtime_port(
        self,
        ctx: RequestContext,
        trace_writer: Optional[TraceWriter] = None,
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
        if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("SOIT_TESTING") == "1":
            from app.adapters.llm.memory import InMemoryLLMPort
            return InMemoryLLMPort()
        providers: Dict[str, LLMPort] = {}

        from app.adapters.llm.openai import OpenAILLMPort
        from app.adapters.llm.deepseek import DeepSeekLLMPort
        from app.adapters.llm.router import LLMRouterPort

        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            providers["openai"] = OpenAILLMPort(api_key=openai_api_key)

        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_api_key:
            providers["deepseek"] = DeepSeekLLMPort(
                api_key=deepseek_api_key,
                base_url=os.getenv("DEEPSEEK_BASE_URL") or settings.deepseek_base_url,
            )

        if not providers:
            logger = logging.getLogger(__name__)
            logger.warning(
                "Neither OPENAI_API_KEY nor DEEPSEEK_API_KEY is set; "
                "falling back to in-memory LLM port."
            )
            from app.adapters.llm.memory import InMemoryLLMPort
            return InMemoryLLMPort()

        return LLMRouterPort(providers=providers)
    
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

        from app.adapters.storage.minio import MinIOStoragePort
        return MinIOStoragePort()
    
    def _create_secrets_port(self) -> SecretsPort:
        """Create Secrets gateway instance.
        
        Returns:
            SecretsPort instance.
        """
        import os
        if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("SOIT_TESTING") == "1":
            from app.adapters.secrets.memory import InMemorySecretsPort
            return InMemorySecretsPort()
        if not settings.vault_url or not settings.vault_token:
            from app.adapters.secrets.memory import InMemorySecretsPort
            return InMemorySecretsPort()
        try:
            from app.adapters.secrets.vault import VaultSecretsPort
        except ModuleNotFoundError:
            logger = logging.getLogger(__name__)
            logger.warning("Vault client not installed; falling back to in-memory secrets port.")
            from app.adapters.secrets.memory import InMemorySecretsPort
            return InMemorySecretsPort()
        return VaultSecretsPort()

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
        return InMemoryEventBus()


# Global container instance
_container: Optional[Container] = None


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
    _container = None
