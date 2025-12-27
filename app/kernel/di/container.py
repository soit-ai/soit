""" container

Dependency injection container for managing Gateway instances.
"""

from typing import Optional, Dict, Any, TypeVar, Type, Callable
from functools import lru_cache

from app.kernel.gateways.llm.interface import LLMGateway
from app.kernel.gateways.tools.interface import ToolGateway
from app.kernel.gateways.vector.interface import VectorGateway
from app.kernel.gateways.storage.interface import StorageGateway
from app.kernel.gateways.secrets.interface import SecretsGateway
from app.kernel.contracts.context import RequestContext
from app.kernel.trace.writer import TraceWriter
from app.kernel.config.settings import settings


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
            "llm_gateway",
            lambda: self._create_llm_gateway(),
        )
        
        # Tool Gateway factory
        self.register_factory(
            "tool_gateway",
            lambda: self._create_tool_gateway(),
        )
        
        # Vector Gateway factory
        self.register_factory(
            "vector_gateway",
            lambda: self._create_vector_gateway(),
        )
        
        # Storage Gateway factory
        self.register_factory(
            "storage_gateway",
            lambda: self._create_storage_gateway(),
        )
        
        # Secrets Gateway factory
        self.register_factory(
            "secrets_gateway",
            lambda: self._create_secrets_gateway(),
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
    
    def get_llm_gateway(
        self,
        ctx: RequestContext,
        trace_writer: Optional[TraceWriter] = None,
    ) -> LLMGateway:
        """Get LLM gateway instance with policy enforcement.
        
        Args:
            ctx: Request context.
            trace_writer: Optional trace writer for audit.
            
        Returns:
            LLMGateway instance wrapped with policy gateway.
        """
        from app.kernel.gateways.llm.policy import LLMPolicyGateway
        
        base_gateway = self.get("llm_gateway")
        return LLMPolicyGateway(
            gateway=base_gateway,
            ctx=ctx,
            trace_writer=trace_writer,
        )
    
    def get_tool_gateway(
        self,
        ctx: RequestContext,
        trace_writer: Optional[TraceWriter] = None,
    ) -> ToolGateway:
        """Get Tool gateway instance with policy enforcement.
        
        Args:
            ctx: Request context.
            trace_writer: Optional trace writer for audit.
            
        Returns:
            ToolGateway instance wrapped with policy gateway.
        """
        from app.kernel.gateways.tools.policy import ToolPolicyGateway
        
        base_gateway = self.get("tool_gateway")
        return ToolPolicyGateway(
            gateway=base_gateway,
            ctx=ctx,
            trace_writer=trace_writer,
        )
    
    def get_vector_gateway(
        self,
        ctx: RequestContext,
        trace_writer: Optional[TraceWriter] = None,
    ) -> VectorGateway:
        """Get Vector gateway instance with policy enforcement.
        
        Args:
            ctx: Request context.
            trace_writer: Optional trace writer for audit.
            
        Returns:
            VectorGateway instance wrapped with policy gateway.
        """
        from app.kernel.gateways.vector.policy import VectorPolicyGateway
        
        base_gateway = self.get("vector_gateway")
        return VectorPolicyGateway(
            gateway=base_gateway,
            ctx=ctx,
            trace_writer=trace_writer,
        )
    
    def get_storage_gateway(
        self,
        ctx: RequestContext,
        trace_writer: Optional[TraceWriter] = None,
    ) -> StorageGateway:
        """Get Storage gateway instance with policy enforcement.
        
        Args:
            ctx: Request context.
            trace_writer: Optional trace writer for audit.
            
        Returns:
            StorageGateway instance wrapped with policy gateway.
        """
        from app.kernel.gateways.storage.policy import StoragePolicyGateway
        
        base_gateway = self.get("storage_gateway")
        return StoragePolicyGateway(
            gateway=base_gateway,
            ctx=ctx,
            trace_writer=trace_writer,
        )
    
    def get_secrets_gateway(
        self,
        ctx: RequestContext,
    ) -> SecretsGateway:
        """Get Secrets gateway instance with policy enforcement.
        
        Args:
            ctx: Request context.
            
        Returns:
            SecretsGateway instance wrapped with policy gateway.
        """
        from app.kernel.gateways.secrets.policy import SecretsPolicyGateway
        
        base_gateway = self.get("secrets_gateway")
        return SecretsPolicyGateway(
            gateway=base_gateway,
            ctx=ctx,
        )
    
    def _create_llm_gateway(self) -> LLMGateway:
        """Create LLM gateway instance.
        
        Returns:
            LLMGateway instance.
        """
        from app.adapters.openai_llm import OpenAILLMGateway
        return OpenAILLMGateway()
    
    def _create_tool_gateway(self) -> ToolGateway:
        """Create Tool gateway instance.
        
        Returns:
            ToolGateway instance.
        """
        from app.adapters.http_tools import HTTPToolsGateway
        return HTTPToolsGateway()
    
    def _create_vector_gateway(self) -> VectorGateway:
        """Create Vector gateway instance.
        
        Returns:
            VectorGateway instance.
        """
        from app.adapters.milvus_vector import MilvusGateway
        return MilvusGateway()
    
    def _create_storage_gateway(self) -> StorageGateway:
        """Create Storage gateway instance.
        
        Returns:
            StorageGateway instance.
        """
        from app.adapters.minio_storage import MinIOStorageGateway
        return MinIOStorageGateway()
    
    def _create_secrets_gateway(self) -> SecretsGateway:
        """Create Secrets gateway instance.
        
        Returns:
            SecretsGateway instance.
        """
        from app.adapters.vault_secrets import VaultSecretsGateway
        return VaultSecretsGateway()


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

