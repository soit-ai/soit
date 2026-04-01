""" settings

Settings model and environment parsing.
"""

from pathlib import Path
from typing import Optional, List
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_PATH = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    project_name: str = "soit"
    """Project name."""
    project_description: str = "SOIT is an agent runtime platform for building, operating, and observing AI systems."
    """Project description."""

    environment: str = "production"
    """Environment."""

    # Database
    database_type: str = "postgresql"
    """Database type."""
    database_host: str = "localhost"
    """Database host."""
    database_port: int = 5432
    """Database port."""
    database_user: Optional[str] = None
    """Database username."""
    database_pass: Optional[str] = None
    """Database password."""
    database_name: str = ""
    """Database name."""
    database_url: Optional[str] = None
    """Database URL."""
    
    # Redis
    redis_host: str = "localhost"
    """Redis host."""
    redis_port: int = 6379
    """Redis port."""
    redis_pass: Optional[str] = None
    """Redis pass."""
    redis_db: int = 0
    """Redis data."""
    redis_url: Optional[str] = None
    """Redis URL for cache and message queue."""
    
    # JWT
    secret_key: str = "your-secret-key-change-in-production"
    """Secret key for JWT token signing."""
    jwt_algorithm: str = "HS256"
    """JWT algorithm."""
    access_token_expire_minutes: int = 30
    """Access token expiration in minutes."""
    
    # Milvus
    milvus_host: str = "localhost"
    """Milvus host."""
    milvus_port: int = 19530
    """Milvus port."""
    
    # MinIO / S3
    minio_endpoint: Optional[str] = None
    """MinIO endpoint URL."""
    minio_access_key: Optional[str] = None
    """MinIO access key."""
    minio_secret_key: Optional[str] = None
    """MinIO secret key."""
    minio_bucket: str = "soit-artifacts"
    """Default bucket name."""
    minio_secure: bool = False
    """Use HTTPS for MinIO."""
    
    # Vault
    vault_url: Optional[str] = None
    """HashiCorp Vault URL."""
    vault_token: Optional[str] = None
    """Vault token."""
    
    # Observability
    sentry_dsn: Optional[str] = None
    """Sentry DSN for error tracking."""
    sentry_enabled: bool = False
    """Enable Sentry error tracking."""
    sentry_traces_sample_rate: float = 0.0
    """Sentry traces sample rate."""
    
    log_level: str = "INFO"
    """Log level (DEBUG, INFO, WARNING, ERROR)."""
    log_format: str = "rich"
    """Log format: text, json, or rich."""
    log_color: bool = True
    """Enable ANSI colors for text logs (TTY only)."""
    log_color_force: bool = True
    """Force ANSI colors even when stdout is not a TTY."""

    default_llm_provider: str = "openai"
    """Default LLM provider when model ref has no provider prefix."""

    deepseek_api_key: Optional[str] = None
    """DeepSeek API key."""

    deepseek_base_url: str = "https://api.deepseek.com"
    """DeepSeek API base URL (OpenAI-compatible)."""

    memory_embedding_model_ref: str = "model:openai:text-embedding-3-small"
    """Default embedding model for memory module."""

    agent_rate_limit_per_minute: Optional[int] = None
    """Optional rate limit for agent runs (per minute)."""

    # Knowledge ingest worker
    knowledge_ingest_worker_enabled: bool = False
    """Enable background knowledge ingestion worker."""

    knowledge_ingest_worker_poll_interval: float = 1.0
    """Polling interval (seconds) for knowledge ingestion worker."""

    knowledge_ingest_worker_max_tasks: int = 10
    """Max tasks to process before worker exits."""

    knowledge_ingest_worker_concurrency: int = 1
    """Max concurrent ingestion tasks per worker loop."""

    knowledge_ingest_worker_heartbeat_seconds: int = 30
    """Heartbeat interval (seconds) for ingest worker logs."""

    # Transactional outbox dispatcher (Phase 1)
    outbox_dispatcher_enabled: bool = False
    """Enable background outbox dispatcher in the API process."""

    outbox_dispatcher_poll_interval: float = 1.0
    """Seconds between outbox dispatcher polls."""

    outbox_dispatcher_batch_limit: int = 50
    """Max outbox rows to attempt per poll."""

    outbox_dispatcher_max_attempts: int = 64
    """Max delivery attempts per row before terminal failure / DLQ."""

    # Plugins
    plugins_dir: str = "./var/plugins"
    """Filesystem directory for plugin packages and extracted installs."""

    plugin_runtime_allow_localhost: bool = False
    """Allow plugin runtime to run on localhost (development only)."""

    platform_version: str = "0.1.0"
    """Platform version for plugin compatibility checks."""

    platform_features: List[str] = []
    """Platform feature flags for plugin compatibility checks."""

    plugin_signature_required: bool = False
    """Require signature verification for plugin package installs."""

    plugin_signature_public_keys: List[str] = []
    """Base64-encoded public keys for plugin signature verification."""

    plugin_integrity_required: bool = False
    """Require digest verification for plugin package installs."""

    # Feature flags
    enable_egress_policy: bool = True
    """Enable egress policy (deny-by-default)."""

    egress_allowlist: List[str] = []
    """Global egress allowlist domains (wildcards supported)."""

    egress_blocklist: List[str] = []
    """Global egress blocklist domains (wildcards supported)."""
    
    # API
    api_v1_prefix: str = "/api/v1"
    """API v1 prefix."""

    # Event bus
    event_bus_backend: str = "memory"
    """Event bus backend: memory or redis."""

    event_bus_redis_url: Optional[str] = None
    """Optional Redis URL override for event bus."""

    event_bus_channel: str = "soit:events"
    """Redis pubsub channel for event bus."""

    @model_validator(mode="after")
    def _build_urls(self) -> "Settings":
        if not self.database_url:
            self.database_url = (
                f"{self.database_type}://{self.database_user}:{self.database_pass}"
                f"@{self.database_host}:{self.database_port}/{self.database_name}"
            )
        if not self.redis_url:
            password = f":{self.redis_pass}@" if self.redis_pass else ""
            self.redis_url = (
                f"redis://{password}{self.redis_host}:{self.redis_port}/{self.redis_db}"
            )
        return self


# Global settings instance
settings = Settings()

def get_settings() -> Settings:
    """Return global Settings instance."""
    return settings

