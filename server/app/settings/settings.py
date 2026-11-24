""" settings

Settings model and environment parsing.
"""

import ipaddress
import json
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_PATH = Path(__file__).resolve().parents[2] / ".env"

PLACEHOLDER_STORAGE_CREDENTIALS = frozenset(
    {"soitminio", "minioadmin", "minio", "change-me", "changeme"}
)
"""Object storage credentials shipped in .env.example and MinIO's own defaults."""

PLACEHOLDER_SECRET_KEYS = frozenset(
    {
        "change-me",
        "your-secret-key-change-in-production",
        # The lite compose file's default, long enough to pass on length alone.
        "soit-lite-evaluation-secret-key-change-me",
    }
)
"""SECRET_KEY values shipped in the repository, refused in production."""

_PRODUCTION_SAFE_DEFAULTS: dict[str, bool] = {
    "response_interaction_inline_execution": False,
    "response_interaction_worker_enabled": True,
    "plugin_signature_required": True,
    "plugin_integrity_required": True,
}
"""Values production takes for these settings when the operator leaves them unset.

Each is the only value production accepts, so asking an operator to type it
added configuration without adding a choice. One set explicitly to anything
else is still refused by `Settings.validate_runtime_requirements`.
"""


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
    database_pool_size: int = 10
    """Connections one process keeps open to PostgreSQL."""
    database_max_overflow: int = 20
    """Extra connections one process may open under load, on top of the pool.

    Every API worker and every worker process (outbox dispatcher, ingest,
    scheduler) holds its own pool, so PostgreSQL's ``max_connections`` must
    cover ``processes x (pool_size + max_overflow)`` plus a margin; see
    docs/operations/database-connections.md.
    """
    database_statement_timeout_ms: int = 120_000
    """Longest one SQL statement may run before PostgreSQL cancels it; 0 disables.

    A backstop, not a tuning knob: no request or worker statement should come
    near it. Migrations open their own connection and are not bound by it.
    """
    database_idle_in_transaction_timeout_ms: int = 300_000
    """How long a session may sit idle inside an open transaction; 0 disables.

    A code path that forgets to end its transaction otherwise holds a pooled
    connection, and any row locks it took, until the process dies. PostgreSQL
    ends such a session after this long and the pool replaces the connection.
    """
    database_lock_timeout_ms: int = 30_000
    """Longest a statement waits for a row or table lock; 0 disables."""

    # Secrets
    secret_value_cache_seconds: float = 60.0
    """How long a resolved secret value is reused in process; 0 disables.

    Rotating or editing a secret takes effect at once whatever this is; it
    bounds only how long a value stays in memory.
    """

    # Model provider HTTP pool
    llm_http_max_connections: int = 200
    """Connections one process may hold open to model providers at once.

    Every streaming call holds one for its whole length, so this caps the
    concurrent model calls of an API or worker process.
    """
    llm_http_max_keepalive_connections: int = 50
    """Idle provider connections kept for reuse."""
    llm_http_keepalive_expiry_seconds: float = 30.0
    """How long an idle provider connection is kept."""

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

    auth_max_failed_attempts: int = Field(default=10, ge=1)
    """Failed password or second-factor attempts an account may make before
    further attempts are refused for ``auth_lockout_seconds``. Also caps the
    password reset mails one address can be sent in that window."""

    auth_lockout_seconds: int = Field(default=900, ge=1)
    """How long an account stays refused after ``auth_max_failed_attempts``,
    counted from its first failure."""

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
    secrets_backend: str = "vault"
    """Where secret values live: `vault`, or `sealed` for evaluation
    installs, which keeps them in the application database sealed with a key
    derived from `SECRET_KEY`. Production requires Vault."""

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

    thread_history_max_messages: int = 200
    """Messages of a conversation branch loaded for an agent turn when nothing narrower is set.

    The branch is walked from its head towards the root and stops here; a
    request's ``context_window_messages`` or a thread's ``max_history_messages``
    narrows it further. Loading the whole ledger made every turn's cost grow
    with the conversation's length.
    """

    log_async: bool = True
    """Write log records from a listener thread instead of the event loop.

    Under docker's json-file driver stdout is a pipe that stalls whenever the
    daemon is busy; a blocking write there stalls every request in the
    process. Off only for synchronous capture (tests force it off).
    """

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

    Applies whenever the resolved route carries no timeout of its own: every
    static (platform-key) provider, and every workspace provider whose
    ``connection_config_json`` sets no ``timeout_ms``. A provider that sets one
    uses it for every call type. Long-form generation regularly exceeds a
    minute, so a flat 60s aborted legitimate requests mid-flight.
    """

    llm_image_timeout_seconds: float = 300.0
    """
    Fallback timeout for a single image generation or edit call, in seconds.

    Applies whenever the resolved route carries no timeout of its own, as for
    ``llm_timeout_seconds``. Image models routinely spend minutes on a
    multi-image request, so the chat fallback is too short; a workspace
    provider's ``timeout_ms`` still bounds its image calls too.
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

    response_interaction_worker_in_api: bool = True
    """Host the interaction worker loop inside each API process.

    Set false when `scripts/response_interaction_worker.py` runs as its own
    service; the worker stays enabled so the API knows executions will happen.
    """

    response_interaction_worker_concurrency: int = 16
    """Interactions one worker process executes at once.

    An execution holds no connection while it waits on the model, but every
    other phase needs one, so this is capped at the pool size plus overflow
    minus four (claim loop and heartbeats). Measured on an 8-core host: 24 in
    flight on a 30-connection pool is the knee for one process; more in
    flight per process only lengthens the queue. Scale by worker replicas.
    """

    response_interaction_worker_drain_seconds: float = 30.0
    """How long a stopping worker lets in-flight interactions finish.

    Executions still running when the grace period ends are cancelled and
    their claims released, so another replica picks them up at once instead
    of after the lease expires.
    """

    response_interaction_worker_metrics_port: int = 9202
    """Prometheus port for the dedicated response interaction worker process."""

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

    # Knowledge connector sync
    knowledge_sync_worker_enabled: bool = True
    """Run the connector sync worker wherever the knowledge ingest worker runs."""

    knowledge_sync_worker_poll_interval: float = 5.0
    """Polling interval (seconds) for queued connector sync runs."""

    knowledge_sync_scheduler_interval_seconds: float = 30.0
    """How often the sync worker looks for sources whose schedule is due."""

    knowledge_sync_worker_concurrency: int = 2
    """Max connector sync runs executing at once per worker loop."""

    knowledge_sync_worker_lease_seconds: int = 300
    """Lease duration held while one connector sync run executes."""

    knowledge_sync_max_attempts: int = 3
    """Times a sync run may be claimed (including crash recovery) before it fails."""

    knowledge_sync_min_interval_seconds: int = 300
    """Shortest allowed gap between two scheduled syncs of one source."""

    knowledge_sync_default_max_items: int = 1000
    """Per-run item cap for a source that sets none."""

    knowledge_sync_max_items_ceiling: int = 20000
    """Highest per-run item cap a source may ask for."""

    knowledge_upload_max_bytes: int = Field(default=100 * 1024 * 1024, ge=1)
    """Largest document accepted by a knowledge upload. An upload past it is
    refused as it streams in, and whatever was already stored is removed."""

    knowledge_sync_default_max_item_bytes: int = 5 * 1024 * 1024
    """Per-item size cap for a source that sets none."""

    knowledge_sync_max_item_bytes_ceiling: int = 50 * 1024 * 1024
    """Highest per-item size cap a source may ask for."""

    knowledge_sync_default_max_total_bytes: int = 256 * 1024 * 1024
    """Per-run download cap for a source that sets none."""

    knowledge_sync_max_total_bytes_ceiling: int = 4 * 1024 * 1024 * 1024
    """Highest per-run download cap a source may ask for."""

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

    # Approvals
    approval_sweeper_enabled: bool = False
    """Close approval requests whose run ended before anyone decided.

    Disabled by default like the other background loops; deployments enable it
    on the API service.
    """

    approval_sweeper_interval: float = 30.0
    """Seconds between approval sweeps."""

    approval_reminder_lead_seconds: float = 3600.0
    """How long before its deadline an undecided request's approvers are reminded.

    A request open for less than twice this is reminded half-way through
    instead; 0 sends no reminders.
    """

    # Image jobs
    image_job_heartbeat_seconds: float = 30.0
    """Seconds between the beats an image call in progress marks its run alive with."""

    image_job_orphan_after_seconds: float = 600.0
    """Seconds without a beat after which an image run counts as lost.

    Well above the heartbeat, and above the default image call timeout, so a
    job started by a process from before the heartbeat existed, during a
    rolling upgrade, is not taken for lost while it still runs.
    """

    image_job_reaper_enabled: bool = False
    """Fail image runs lost with the process that ran them.

    An image job runs in the process that accepted it; a restart loses it and
    leaves its run queued or running for good. The reaper fails such a run and
    charges the provider call it left in flight. Disabled by default like the
    other background loops; deployments enable it on the API service.
    """

    image_job_reaper_interval: float = 60.0
    """Seconds between lost image run sweeps."""

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

    outbox_retention_days: int = 7
    """Dispatched outbox rows and consumer checkpoints older than this are purged."""

    outbox_retention_interval_seconds: float = 3600.0
    """Seconds between outbox retention passes."""

    usage_reconcile_interval_seconds: float = 3600.0
    """Seconds between checks for a finished UTC day whose usage aggregates
    have not been rebuilt from the cost ledger yet."""

    outbox_retention_batch_size: int = 1000
    """Rows deleted per statement during a retention pass."""

    metrics_token: str | None = None
    """Optional bearer token required to scrape GET /metrics. When unset, /metrics is
    open and must be protected at the network layer (internal interface / firewall)."""

    allow_public_registration: bool = True
    """Allow unauthenticated POST /register self-signup. Enterprise deployments can set
    this to false to require admin-provisioned users (also removes email enumeration)."""

    # Plugins
    plugins_dir: str = "./var/plugins"
    """Filesystem directory for plugin packages and extracted installs."""

    plugin_package_max_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    """Largest plugin package (the uploaded zip) accepted."""

    plugin_package_max_extracted_bytes: int = Field(default=200 * 1024 * 1024, ge=1)
    """Largest total a plugin package may unpack to, so a small archive that
    expands to fill the disk is refused before anything is written."""

    plugin_package_max_entries: int = Field(default=5000, ge=1)
    """Most files and directories a plugin package may contain."""

    plugin_runtime_allow_localhost: bool = False
    """Allow plugin runtime to run on localhost (development only)."""

    platform_version: str = "1.8.0"
    """Platform version for plugin compatibility checks."""

    platform_edition: str = "community"
    """Current product edition: community, enterprise, or cloud."""

    telemetry_enabled: bool = False
    """Send one anonymous usage report a day (``docs/telemetry.md``). Off unless set."""

    telemetry_endpoint: str = "https://soit.ai/api/telemetry"
    """Where the daily report goes when telemetry is on."""

    soit_role: str = "all"
    """What this process serves (``SOIT_ROLE``).

    ``all``, the default, serves the whole API and runs the background work.
    ``gateway`` serves only the entry points external callers use (``/v1``,
    ``/mcp``, ``/api/v1/tools``) and health, and runs no background work, so
    the gateway can be scaled and exposed apart from the console's API; a
    process with the default role must run beside it.
    """

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

    egress_private_networks: list[str] = []
    """Private or loopback networks (CIDR) governed calls may reach.

    Outbound calls to a private, loopback or otherwise non-public address are
    refused, which also keeps out a model server inside your own network (a
    local Ollama, an on-premises vLLM). An address in one of these networks is
    let through; the target still needs an egress allowlist entry like any
    other. Empty, the default, refuses every non-public address.
    """

    # API
    api_v1_prefix: str = "/api/v1"
    """API v1 prefix."""

    trusted_proxies: list[str] = []
    """Addresses or CIDR ranges of the proxies in front of the API.

    ``X-Forwarded-For`` is read only when the connection comes from one of
    them, and then from the right, skipping trusted hops, so a client cannot
    choose the address an API key's IP allowlist sees. Empty means the socket
    peer is the client.
    """

    mcp_resource_url: str = ""
    """Public URL of the MCP endpoint, e.g. ``https://soit.example.com/mcp``.

    Named in the OAuth protected resource metadata and in the challenge an
    unauthenticated MCP client gets. Empty derives it from the request, which
    is right unless a proxy in front rewrites the scheme or host.
    """

    mcp_authorization_servers: list[str] = []
    """OAuth authorization servers whose access tokens this deployment accepts
    at the MCP endpoint, listed in its protected resource metadata. Empty
    lists none, and MCP clients authenticate with SOIT API keys.
    """

    mcp_allowed_origins: list[str] = []
    """Browser origins, besides the endpoint's own, that may call the MCP
    endpoint. Clients that are not browsers send no Origin and are unaffected.
    """

    # Event bus
    event_bus_backend: str = "memory"
    """Event bus backend: memory or redis."""

    event_bus_redis_url: str | None = None
    """Optional Redis URL override for event bus."""

    event_bus_channel: str = "soit:events"
    """Redis pubsub channel for event bus."""

    @field_validator("soit_role")
    @classmethod
    def _known_role(cls, value: str) -> str:
        role = value.strip().lower()
        if role not in ("all", "gateway"):
            raise ValueError(f"SOIT_ROLE must be all or gateway, not {value!r}")
        return role

    @field_validator("egress_private_networks")
    @classmethod
    def _valid_private_networks(cls, value: list[str]) -> list[str]:
        networks: list[str] = []
        for entry in value:
            try:
                network = ipaddress.ip_network(entry.strip(), strict=False)
            except ValueError as exc:
                raise ValueError(f"EGRESS_PRIVATE_NETWORKS entry is not a CIDR: {entry}") from exc
            if network.prefixlen == 0:
                raise ValueError(f"EGRESS_PRIVATE_NETWORKS entry would open every address: {entry}")
            networks.append(str(network))
        return networks

    @field_validator("trusted_proxies")
    @classmethod
    def _valid_trusted_proxies(cls, value: list[str]) -> list[str]:
        # A malformed entry would silently trust nothing, or be read as some
        # other range; refuse it at startup instead.
        for entry in value:
            try:
                ipaddress.ip_network(entry.strip(), strict=False)
            except ValueError as exc:
                raise ValueError(f"TRUSTED_PROXIES entry is not an address or CIDR: {entry}") from exc
        return [entry.strip() for entry in value]

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
    def _apply_production_defaults(self) -> "Settings":
        if (self.environment or "").strip().lower() != "production":
            return self
        for name, value in _PRODUCTION_SAFE_DEFAULTS.items():
            if name not in self.model_fields_set:
                setattr(self, name, value)
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

    @model_validator(mode="after")
    def _validate_secrets_backend(self) -> "Settings":
        backend = (self.secrets_backend or "").strip().lower()
        if backend not in {"vault", "sealed"}:
            raise ValueError("SECRETS_BACKEND must be 'vault' or 'sealed'")
        self.secrets_backend = backend
        return self

    def runtime_warnings(self) -> list[str]:
        """Production choices that are allowed but worth saying out loud at startup."""
        if (self.environment or "").strip().lower() != "production":
            return []
        warnings: list[str] = []
        if not self.otel_enabled:
            warnings.append(
                "OpenTelemetry tracing is off; runs, costs and audit are still recorded, "
                "but no traces are exported"
            )
        if self.secrets_backend == "sealed":
            warnings.append(
                "Secret values are sealed in PostgreSQL with a key derived from SECRET_KEY: "
                "back up SECRET_KEY with the database, and never change it, or every stored "
                "secret becomes unreadable"
            )
        if self.plugin_signature_required and not self.plugin_signature_public_keys:
            warnings.append(
                "No PLUGIN_SIGNATURE_PUBLIC_KEYS: third-party plugin packages cannot be installed"
            )
        return warnings

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
        # pgvector keeps vectors in the application database, which is what
        # the lite profile runs in production; Milvus is the choice for
        # collections too large for it.
        if self.vector_backend == "milvus" and self.milvus_mode == "lite":
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
        # With no trusted key every third-party package is refused, which
        # fails closed; runtime_warnings says so at startup.
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
        if self.otel_enabled and not (self.otel_exporter_otlp_endpoint or "").strip():
            raise ValueError("Production requires an OpenTelemetry OTLP endpoint when tracing is on")
        # Sealed secrets (the lite profile) keep values in PostgreSQL behind a
        # key derived from SECRET_KEY; Vault is required only when chosen.
        if self.secrets_backend == "vault" and (not self.vault_url or not self.vault_token):
            raise ValueError("Production requires Vault URL and token")
        secret_key = (self.secret_key or "").strip()
        if len(secret_key) < 32 or secret_key in PLACEHOLDER_SECRET_KEYS:
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

