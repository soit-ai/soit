""" settings

Settings model and environment parsing.
"""

from pathlib import Path
from urllib.parse import urlparse

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
    database_user: str | None = None
    """Database username."""
    database_pass: str | None = None
    """Database password."""
    database_name: str = ""
    """Database name."""
    database_url: str | None = None
    """Database URL."""

    # Redis
    redis_host: str = "localhost"
    """Redis host."""
    redis_port: int = 6379
    """Redis port."""
    redis_pass: str | None = None
    """Redis pass."""
    redis_db: int = 0
    """Redis data."""
    redis_url: str | None = None
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

    # Storage (fsspec)
    storage_url: str | None = None
    """fsspec storage root URL."""
    storage_options_json: str = "{}"
    """JSON object with fsspec storage options."""
    storage_auto_mkdir: bool = True
    """Create storage parent directories when supported."""
    storage_operation_timeout_seconds: float = 10.0
    """Maximum seconds to wait for a single storage filesystem operation."""

    # Vault
    vault_url: str | None = None
    """HashiCorp Vault URL."""
    vault_token: str | None = None
    """Vault token."""

    # Observe
    sentry_dsn: str | None = None
    """Sentry DSN for error tracking."""
    sentry_enabled: bool = False
    """Enable Sentry error tracking."""
    sentry_traces_sample_rate: float = 0.0
    """Sentry traces sample rate."""

    # OpenTelemetry
    otel_enabled: bool = False
    """Enable OpenTelemetry SDK instrumentation and OTLP export."""

    otel_service_name: str = "soit-api"
    """OpenTelemetry service.name for the API process."""

    otel_exporter_otlp_endpoint: str = "http://localhost:4318/v1/traces"
    """OTLP/HTTP trace export endpoint."""

    otel_traces_sample_ratio: float = 1.0
    """Parent-based trace sampling ratio from zero to one."""

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

    llm_timeout_seconds: float = 180.0
    """
    Default timeout for a single LLM call, in seconds.

    Applies whenever the resolved route carries no timeout of its own, which is the
    case for every static (platform-key) provider. Long-form generation regularly
    exceeds a minute, so the previous hard-coded 60s aborted legitimate requests
    mid-flight; workspace-configured providers still override this per route.
    """

    openai_api_key: str | None = None
    """OpenAI API key."""

    deepseek_api_key: str | None = None
    """DeepSeek API key."""

    deepseek_base_url: str = "https://api.deepseek.com"
    """DeepSeek API base URL (OpenAI-compatible)."""

    anthropic_api_key: str | None = None
    """Anthropic API key."""

    anthropic_base_url: str = "https://api.anthropic.com"
    """Anthropic API base URL."""

    memory_embedding_model_ref: str = "model:openai:text-embedding-3-small"
    """Default embedding model for memory module."""

    agent_rate_limit_per_minute: int | None = None
    """Optional rate limit for agent runs (per minute)."""

    credit_rates_json: str = '{"USD": "1000"}'
    """JSON map of currency code to credits deducted per one currency unit."""

    credit_enforcement_enabled: bool = False
    """Block metered invocations when the workspace credit balance is exhausted."""

    credit_low_balance_threshold: float = 100.0
    """Warn on metered invocations when the balance falls below this many credits."""

    response_interaction_inline_execution: bool = True
    """Execute claimed chat interactions inline; development and tests only."""

    response_interaction_worker_enabled: bool = False
    """Enable the durable database-backed chat interaction worker."""

    response_interaction_worker_poll_interval: float = 0.25
    """Polling interval for the durable chat interaction worker."""

    response_interaction_worker_concurrency: int = 4
    """Number of durable chat interaction workers in each API process."""

    response_interaction_lease_seconds: int = 90
    """Lease duration for one durable chat interaction claim."""

    # Knowledge ingest worker
    knowledge_ingest_worker_enabled: bool = False
    """Enable background knowledge ingestion worker."""

    knowledge_ingest_worker_poll_interval: float = 1.0
    """Polling interval (seconds) for knowledge ingestion worker."""

    knowledge_ingest_worker_max_tasks: int = 0
    """Max tasks to process before the worker exits; 0 runs without a limit."""

    knowledge_ingest_worker_concurrency: int = 1
    """Max concurrent ingestion tasks per worker loop."""

    knowledge_ingest_worker_heartbeat_seconds: int = 30
    """Heartbeat interval (seconds) for ingest worker logs."""

    knowledge_ingest_worker_lease_seconds: int = 120
    """Lease duration held while one ingestion task executes."""

    # Workflow execution
    workflow_execution_lease_seconds: int = 120
    """Lease duration renewed while a workflow execution is running."""

    workflow_orphan_reaper_enabled: bool = False
    """Fail workflow runs whose execution lease expired without renewal.

    Disabled by default like the other background loops; deployments enable it
    on the API service, which exists in every topology.
    """

    workflow_orphan_reaper_interval: float = 30.0
    """Seconds between orphaned workflow run sweeps."""

    # Transactional outbox dispatcher (Phase 1)
    outbox_dispatcher_enabled: bool = False
    """Enable background outbox dispatcher in the API process."""

    outbox_dispatcher_poll_interval: float = 1.0
    """Seconds between outbox dispatcher polls."""

    outbox_dispatcher_batch_limit: int = 50
    """Max outbox rows to attempt per poll."""

    outbox_dispatcher_max_attempts: int = 64
    """Max delivery attempts per row before terminal failure / DLQ."""

    outbox_dispatcher_lease_seconds: int = 60
    """Seconds before an abandoned outbox claim can be reclaimed."""

    outbox_dispatcher_metrics_port: int = 9201
    """Prometheus and liveness HTTP port for the dedicated dispatcher."""

    metrics_token: str | None = None
    """Optional bearer token required to scrape GET /metrics. When unset, /metrics is
    open and must be protected at the network layer (internal interface / firewall)."""

    allow_public_registration: bool = True
    """Allow unauthenticated POST /register self-signup. Enterprise deployments can set
    this to false to require admin-provisioned users (also removes email enumeration)."""

    # Plugins
    plugins_dir: str = "./var/plugins"
    """Filesystem directory for plugin packages and extracted installs."""

    plugin_runtime_allow_localhost: bool = False
    """Allow plugin runtime to run on localhost (development only)."""

    platform_version: str = "1.0.0"
    """Platform version for plugin compatibility checks."""

    platform_edition: str = "community"
    """Current product edition: community, enterprise, or cloud."""

    platform_entitlements: list[str] = []
    """License or control-plane granted feature keys."""

    enterprise_license_path: str | None = None
    """Optional signed Enterprise license file mounted into this runtime."""

    enterprise_license_public_key_path: str | None = None
    """Optional Ed25519 public key path used to verify the Enterprise license."""

    plugin_signature_required: bool = False
    """Require signature verification for plugin package installs."""

    plugin_signature_public_keys: list[str] = []
    """Base64-encoded public keys for plugin signature verification."""

    plugin_integrity_required: bool = False
    """Require digest verification for plugin package installs."""

    # Feature flags
    enable_egress_policy: bool = True
    """Enable egress policy (deny-by-default)."""

    egress_allowlist: list[str] = []
    """Global egress allowlist domains (wildcards supported)."""

    egress_blocklist: list[str] = []
    """Global egress blocklist domains (wildcards supported)."""

    # API
    api_v1_prefix: str = "/api/v1"
    """API v1 prefix."""

    # Event bus
    event_bus_backend: str = "memory"
    """Event bus backend: memory or redis."""

    event_bus_redis_url: str | None = None
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

    def validate_runtime_requirements(self) -> None:
        """Fail closed when production runtime dependencies are not configured."""
        if (self.environment or "").strip().lower() != "production":
            return
        database = urlparse(self.database_url or "")
        if not all(
            [
                database.scheme,
                database.hostname,
                database.username,
                database.password,
                database.path.strip("/"),
            ]
        ):
            raise ValueError("Production database URL must include host, database, and credentials")
        if (self.event_bus_backend or "").strip().lower() != "redis":
            raise ValueError("Production requires the Redis event bus backend")
        if self.outbox_dispatcher_enabled:
            raise ValueError("Production requires the dedicated outbox dispatcher process")
        if self.response_interaction_inline_execution:
            raise ValueError("Production forbids inline chat interaction execution")
        if not self.response_interaction_worker_enabled:
            raise ValueError("Production requires the durable chat interaction worker")
        if not self.otel_enabled:
            raise ValueError("Production requires OpenTelemetry tracing")
        if not (self.otel_exporter_otlp_endpoint or "").strip():
            raise ValueError("Production requires an OpenTelemetry OTLP endpoint")
        if not self.vault_url or not self.vault_token:
            raise ValueError("Production requires Vault URL and token")
        if not any(
            [
                self.openai_api_key,
                self.deepseek_api_key,
                self.anthropic_api_key,
            ]
        ):
            raise ValueError("Production requires at least one LLM provider key")
        secret_key = (self.secret_key or "").strip()
        if len(secret_key) < 32 or secret_key in {
            "change-me",
            "your-secret-key-change-in-production",
        }:
            raise ValueError("Production requires a non-placeholder SECRET_KEY of at least 32 characters")


# Global settings instance
settings = Settings()

def get_settings() -> Settings:
    """Return global Settings instance."""
    return settings

