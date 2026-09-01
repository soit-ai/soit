""" settings

Settings model and environment parsing.
"""

import json
from pathlib import Path
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_PATH = Path(__file__).resolve().parents[2] / ".env"

PLACEHOLDER_STORAGE_CREDENTIALS = frozenset(
    {"soitminio", "minioadmin", "minio", "change-me", "changeme"}
)
"""Object storage credentials shipped in .env.example and MinIO's own defaults."""


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
    """Access token expiration in minutes.

    Short by design: a revoked session keeps working until the access token it
    issued expires, so this value is the worst-case delay on a sign-out. The
    refresh flow renews silently, so shortening it costs the user nothing.
    """

    refresh_token_expire_days: int = 14
    """How long a session can be renewed before the user signs in again."""

    schedule_worker_enabled: bool = False
    """Fire due schedules from this process.

    Off by default so a development instance does not start running somebody's
    hourly jobs. Production turns it on; several replicas may run it, and the
    claim ensures each occurrence fires once.
    """

    schedule_worker_poll_interval: float = 15.0
    """Seconds between sweeps. Cron resolution is a minute, so this is ample."""

    schedule_worker_lease_seconds: int = 60
    """How long a claimed schedule stays claimed if the worker dies."""

    system_mail_enabled: bool = False
    """Whether the instance can send its own mail.

    Off by default. Password resets, invitations and address verification each
    report that they are unavailable rather than accepting a request and
    dropping it, which is what a silent no-op would do.
    """

    system_mail_url: str = ""
    """Apprise URL for instance mail, e.g. mailto://user:pass@smtp.host.

    Carries credentials, so it is never logged or returned by an endpoint.
    """

    system_mail_link_base_url: str = ""
    """Public base URL used to build links in mail. Falls back to the request."""

    account_deletion_grace_days: int = 7
    """How long a closure request can be withdrawn before it takes effect."""

    account_deletion_sweeper_enabled: bool = False
    """Close accounts whose pause has elapsed, without an operator clicking.

    Off by default so a self-hosted deployment does not start closing accounts
    on a timer nobody knew was running. Production turns it on.
    """

    account_deletion_sweeper_interval: float = 3600.0
    """Seconds between sweeps. A closure is due within a day, not a second."""

    # Vector store
    vector_backend: str = "milvus"
    """Vector store backend: `milvus` or `pgvector`.

    `pgvector` keeps collections as tables in PostgreSQL, which is what local
    development uses when it already runs PostgreSQL and would rather not run
    Milvus. Production runs `milvus`.
    """
    pgvector_url: str | None = None
    """PostgreSQL URL for the vector store. Falls back to `database_url`."""
    pgvector_schema: str = "vector_store"
    """Schema holding the pgvector collection tables."""

    # Milvus
    milvus_mode: str = "server"
    """Vector store mode: `server` for a Milvus deployment, `lite` for Milvus Lite.

    `lite` is a local debugging switch. It runs the embedded Milvus Lite engine
    against a file on disk, so knowledge and retrieval work without the Milvus,
    etcd and MinIO containers. It is single-process, holds no data anyone else
    can read, and is rejected in production by `validate_runtime_requirements`.
    """
    milvus_host: str = "localhost"
    """Milvus host. Used when `milvus_mode` is `server`."""
    milvus_port: int = 19530
    """Milvus port. Used when `milvus_mode` is `server`."""
    milvus_lite_file: str = "./.milvus/soit_lite.db"
    """Milvus Lite database file. Used when `milvus_mode` is `lite`.

    A relative path resolves against the working directory of the process, which
    for local development is `server/`. The parent directory is created on first
    connect.
    """

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

    llm_image_timeout_seconds: float = 300.0
    """
    Fallback timeout for a single image generation call, in seconds.

    Applies whenever the resolved route carries no timeout of its own. Image
    models routinely spend minutes on a multi-image request, so the chat
    fallback is too short; workspace-configured providers still override this
    per route.
    """

    llm_image_max_retries: int = 0
    """
    Retry ceiling for image generation, capping the per-route retry budget.

    Image generation is billed per generated image and is not idempotent: a
    platform-side timeout does not cancel the provider-side generation, so a
    retry can bill the workspace again while the platform records a single
    usage fact. Zero keeps recorded cost aligned with provider charges.
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

    evaluation_judge_model_ref: str = ""
    """Default model for LLM-as-judge regression scoring.

    Empty disables the judge; cases that declare an llm_judge expectation then
    fail with llm_judge_unconfigured instead of silently passing.
    """

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

    plugin_revoked_package_digests: list[str] = []
    """Package digests refused on install even when correctly signed.

    Removing a compromised key from the trusted set cannot un-trust artifacts
    already signed with it, so revocation is expressed per artifact.
    """

    plugin_integrity_required: bool = False
    """Require digest verification for plugin package installs."""

    # Content safety / PII
    content_safety_enabled: bool = True
    """Inspect content for credentials and personal identifiers."""

    content_safety_provider: str = "builtin"
    """Which provider inspects content: builtin or http.

    "builtin" is deterministic pattern matching that runs in-process and needs
    no service. It finds credentials and the identifiers that are personal data
    everywhere; it cannot judge tone, intent or confidentiality. A deployment
    that needs a classifier sets this to "http" and points at one.
    """

    content_safety_secret_action: str = "redact"
    """What to do when a credential is found: observe, redact or block."""

    content_safety_pii_action: str = "observe"
    """What to do when personal data is found: observe, redact or block.

    Recording by default. Personal data is the ordinary content of real work --
    a support agent reading a customer's address is the job -- so rewriting it
    silently would corrupt the work while looking like nothing happened.
    """

    content_safety_endpoint: str | None = None
    """HTTP endpoint of the external classifier the deployment operates."""

    content_safety_api_key: str | None = None
    """Optional bearer token for the classifier."""

    content_safety_timeout_seconds: float = 10.0
    """Per-inspection timeout."""

    content_safety_fail_closed: bool = True
    """Refuse content when the classifier is unreachable."""

    content_safety_inspect_inbound: bool = True
    """Inspect content entering the runtime."""

    content_safety_inspect_outbound: bool = True
    """Inspect content leaving the runtime."""

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

    @model_validator(mode="after")
    def _validate_vector_store(self) -> "Settings":
        backend = (self.vector_backend or "").strip().lower()
        if backend not in {"milvus", "pgvector"}:
            raise ValueError("VECTOR_BACKEND must be 'milvus' or 'pgvector'")
        self.vector_backend = backend

        mode = (self.milvus_mode or "").strip().lower()
        if mode not in {"server", "lite"}:
            raise ValueError("MILVUS_MODE must be 'server' or 'lite'")
        self.milvus_mode = mode
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
        if self.vector_backend != "milvus":
            # pgvector is a development convenience that puts the vector store
            # in the application database. Production runs the vector store the
            # deployment profile provisions and operates.
            raise ValueError("Production requires the Milvus vector backend")
        if self.milvus_mode == "lite":
            # Milvus Lite is a single-process file store meant for local
            # debugging. Nothing else can read it, so it must not be what a
            # production deployment silently falls back to.
            raise ValueError("Production requires a Milvus server, not Milvus Lite")
        if self.outbox_dispatcher_enabled:
            raise ValueError("Production requires the dedicated outbox dispatcher process")
        if self.response_interaction_inline_execution:
            raise ValueError("Production forbids inline chat interaction execution")
        if not self.response_interaction_worker_enabled:
            raise ValueError("Production requires the durable chat interaction worker")
        if not self.plugin_signature_required:
            raise ValueError("Production requires plugin signature verification")
        if not self.plugin_signature_public_keys:
            # Requiring signatures with no trusted key rejects every package,
            # which reads as a signature gate but is really a total block.
            raise ValueError(
                "Production requires at least one plugin signature public key"
            )
        if not self.plugin_integrity_required:
            raise ValueError("Production requires plugin package digest verification")
        if (
            self.content_safety_enabled
            and self.content_safety_provider == "http"
            and not (self.content_safety_endpoint or "").strip()
        ):
            # An external provider with no endpoint inspects nothing while
            # reporting that inspection is on, which is worse than declaring it
            # unavailable. The built-in provider needs no endpoint.
            raise ValueError("Content safety is set to http but no endpoint is configured")
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
        try:
            storage_options = json.loads(self.storage_options_json or "{}")
        except json.JSONDecodeError as exc:
            # Skipping the credential check on unparseable options would report a
            # verified store while the deployment still runs the shipped defaults.
            raise ValueError("Production requires STORAGE_OPTIONS_JSON to be a JSON object") from exc
        if not isinstance(storage_options, dict):
            raise ValueError("Production requires STORAGE_OPTIONS_JSON to be a JSON object")
        for field in ("key", "secret"):
            # Absent credentials are left alone: they mean the backend supplies its
            # own identity, not that a placeholder was shipped.
            if str(storage_options.get(field) or "").strip().lower() in PLACEHOLDER_STORAGE_CREDENTIALS:
                raise ValueError("Production requires non-placeholder object storage credentials")


# Global settings instance
settings = Settings()

def get_settings() -> Settings:
    """Return global Settings instance."""
    return settings

