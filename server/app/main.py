""" main

FastAPI application entry point.
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Add project root to Python path
# This ensures 'app' module can be found when running main.py directly
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(project_root / ".env")

from app.kernel.commons.errors import KernelError  # noqa: E402
from app.kernel.observe.context import get_log_context  # noqa: E402
from app.kernel.observe.logging import setup_logging  # noqa: E402
from app.kernel.observe.sentry import setup_sentry  # noqa: E402
from app.middleware.error_handler import (  # noqa: E402
    ERROR_CODE_TO_STATUS,
    ErrorHandlerMiddleware,
)
from app.middleware.request_id import RequestIdMiddleware  # noqa: E402
from app.middleware.response_envelope import (  # noqa: E402
    ResponseEnvelopeMiddleware,
    error_envelope,
)
from app.middleware.tracing import TracingMiddleware  # noqa: E402
from app.settings.settings import settings as app_settings  # noqa: E402

# Setup logging
setup_logging()

# Setup Sentry
setup_sentry()
logger = logging.getLogger(__name__)


def _handle_startup_failure(component: str, exc: Exception) -> None:
    """Fail production startup while keeping development diagnostics available."""
    if (app_settings.environment or "").strip().lower() == "production":
        raise RuntimeError(f"Failed to initialize {component}") from exc
    logger.exception("Startup component initialization failed", extra={"component": component})


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    _ = app
    app_settings.validate_runtime_requirements()
    # Startup
    # Create database tables if needed
    # create_tables()

    # Load installed plugins into runtime registry
    try:
        from app.modules.plugin.runtime.loader import PluginRuntimeLoader
        PluginRuntimeLoader().load_all()
    except Exception as exc:
        _handle_startup_failure("plugin registry", exc)

    try:
        from app.wiring.outbox_handlers import register_outbox_handlers

        register_outbox_handlers()
    except Exception as exc:
        _handle_startup_failure("outbox handlers", exc)

    try:
        from app.wiring.task_drivers import register_task_drivers

        register_task_drivers()
    except Exception as exc:
        _handle_startup_failure("task drivers", exc)

    knowledge_worker = None
    if getattr(app_settings, "knowledge_ingest_worker_enabled", False):
        try:
            from app.modules.knowledge.runtime.ingest_worker import (
                GlobalKnowledgeIngestWorker,
            )

            knowledge_worker = GlobalKnowledgeIngestWorker()
        except Exception as exc:
            _handle_startup_failure("knowledge ingest worker", exc)

    outbox_service = None
    if getattr(app_settings, "outbox_dispatcher_enabled", False):
        try:
            from app.infra.db.session import get_db_sync
            from app.kernel.events.dispatcher import OutboxDispatcherService
            from app.wiring.outbox_handlers import get_outbox_registry

            outbox_service = OutboxDispatcherService(
                get_outbox_registry(),
                db_factory=get_db_sync,
                batch_limit=max(1, int(app_settings.outbox_dispatcher_batch_limit)),
                max_dispatch_attempts=max(1, int(app_settings.outbox_dispatcher_max_attempts)),
            )
        except Exception as exc:
            _handle_startup_failure("outbox dispatcher", exc)

    response_interaction_workers = []
    if getattr(app_settings, "response_interaction_worker_enabled", False):
        try:
            from app.wiring.response_interaction_worker import (
                GlobalResponseInteractionWorker,
            )

            response_interaction_workers = [
                GlobalResponseInteractionWorker()
                for _ in range(
                    max(
                        1,
                        int(app_settings.response_interaction_worker_concurrency),
                    )
                )
            ]
        except Exception as exc:
            _handle_startup_failure("response interaction worker", exc)

    background_tasks: list[asyncio.Task] = []
    try:
        if knowledge_worker is not None:
            background_tasks.append(
                asyncio.create_task(
                    knowledge_worker.run_loop(
                        poll_interval=max(
                            0.1,
                            app_settings.knowledge_ingest_worker_poll_interval,
                        ),
                        # A long-running API process must keep ingesting; a
                        # positive limit is only meaningful for bounded runs.
                        max_tasks=app_settings.knowledge_ingest_worker_max_tasks
                        or None,
                        concurrency=app_settings.knowledge_ingest_worker_concurrency,
                    )
                )
            )
        if outbox_service is not None:
            background_tasks.append(
                asyncio.create_task(
                    outbox_service.run_loop(
                        poll_interval_seconds=max(
                            0.05,
                            float(app_settings.outbox_dispatcher_poll_interval),
                        ),
                    )
                )
            )
        for response_interaction_worker in response_interaction_workers:
            background_tasks.append(
                asyncio.create_task(
                    response_interaction_worker.run_loop(
                        poll_interval=max(
                            0.05,
                            float(app_settings.response_interaction_worker_poll_interval),
                        )
                    )
                )
            )

        yield
    finally:
        for task in background_tasks:
            task.cancel()
        for task in background_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass


# Create FastAPI application
from app.docs.openapi import tags_metadata  # noqa: E402

app = FastAPI(
    title=getattr(app_settings, "PROJECT_NAME", "SOIT API"),
    description="SOIT LLM Development Platform API",
    version=app_settings.platform_version,
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    tags_metadata=tags_metadata,
)

from app.infra.telemetry import configure_telemetry  # noqa: E402

configure_telemetry(app)

# Setup tracing middleware before app startup
app.add_middleware(TracingMiddleware)
# Add middleware (order matters: first added is last executed)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(ResponseEnvelopeMiddleware)
app.add_middleware(RequestIdMiddleware)

# Configure CORS
cors_origins = getattr(app_settings, "CORS_ORIGINS", ["*"])
if isinstance(cors_origins, str):
    cors_origins = [cors_origins]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers ensure consistent error envelopes across dependencies and routes.
def _resolve_trace_ids(request: Request) -> tuple[str | None, str | None]:
    log_ctx = get_log_context()
    request_id = getattr(request.state, "request_id", None) or log_ctx.get("request_id")
    run_id = getattr(request.state, "run_id", None) or log_ctx.get("run_id")
    return request_id, run_id


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    status_to_code = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    error_code = status_to_code.get(exc.status_code, "HTTP_ERROR")
    request_id, run_id = _resolve_trace_ids(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope(
            code=error_code,
            message=str(exc.detail) if exc.detail else f"HTTP {exc.status_code}",
            request_id=request_id,
            run_id=run_id,
        ),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error.get("loc", [])),
            "message": error.get("msg", "Validation error"),
            "type": error.get("type", "validation_error"),
        })
    request_id, run_id = _resolve_trace_ids(request)
    return JSONResponse(
        status_code=400,
        content=error_envelope(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details={"errors": errors},
            request_id=request_id,
            run_id=run_id,
        ),
    )


@app.exception_handler(KernelError)
async def kernel_exception_handler(request: Request, exc: KernelError) -> JSONResponse:
    error_code = exc.code
    status_code = ERROR_CODE_TO_STATUS.get(error_code, 500)
    request_id, run_id = _resolve_trace_ids(request)
    return JSONResponse(
        status_code=status_code,
        content=error_envelope(
            code=error_code,
            message=exc.message,
            details=exc.details,
            request_id=request_id,
            run_id=run_id,
        ),
    )


# Register routers
from app.api.v1.agent.router import router as agent_router  # noqa: E402
from app.api.v1.agent.thread_router import router as thread_router  # noqa: E402
from app.api.v1.attachments.router import router as attachments_router  # noqa: E402
from app.api.v1.billing.router import router as billing_router  # noqa: E402
from app.api.v1.diagnostics.router import router as diagnostics_router  # noqa: E402
from app.api.v1.evaluation.router import router as evaluation_router  # noqa: E402
from app.api.v1.feedback.router import router as feedback_router  # noqa: E402
from app.api.v1.health.router import router as health_router  # noqa: E402
from app.api.v1.identity.router import router as identity_router  # noqa: E402
from app.api.v1.knowledge.router import router as knowledge_router  # noqa: E402
from app.api.v1.modelhub.router import router as modelhub_router  # noqa: E402
from app.api.v1.notification.router import router as notification_router  # noqa: E402
from app.api.v1.observe.router import router as observe_router  # noqa: E402
from app.api.v1.plugin.router import router as plugin_router  # noqa: E402
from app.api.v1.responses.router import router as responses_router  # noqa: E402
from app.api.v1.run.router import router as run_router  # noqa: E402
from app.api.v1.search.router import router as search_router  # noqa: E402
from app.api.v1.secrets.router import router as secrets_router  # noqa: E402
from app.api.v1.security.router import router as security_router  # noqa: E402
from app.api.v1.task.router import router as task_router  # noqa: E402
from app.api.v1.workflow.router import router as workflow_router  # noqa: E402
from app.docs.openapi import install_enveloped_openapi  # noqa: E402

# Register routers
app.include_router(identity_router, prefix="/api/v1", tags=["identity"])
app.include_router(workflow_router, prefix="/api/v1/workflows", tags=["workflows"])
app.include_router(knowledge_router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(modelhub_router, prefix="/api/v1/modelhub", tags=["modelhub"])
app.include_router(plugin_router, prefix="/api/v1/plugins", tags=["plugins"])
app.include_router(observe_router, prefix="/api/v1/observe", tags=["observe"])
app.include_router(run_router, prefix="/api/v1/runs", tags=["runs"])
app.include_router(security_router, prefix="/api/v1/security", tags=["security"])
app.include_router(secrets_router, prefix="/api/v1/secrets", tags=["secrets"])
app.include_router(health_router, tags=["health"])
app.include_router(agent_router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(task_router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(thread_router, prefix="/api/v1/threads", tags=["threads"])
app.include_router(evaluation_router, prefix="/api/v1/evaluations", tags=["evaluations"])
app.include_router(feedback_router, prefix="/api/v1/feedback", tags=["feedback"])
app.include_router(diagnostics_router, prefix="/api/v1/diagnostics", tags=["diagnostics"])
app.include_router(search_router, prefix="/api/v1/search", tags=["search"])
app.include_router(notification_router, prefix="/api/v1/notifications", tags=["notifications"])
app.include_router(responses_router, prefix="/api/v1/responses", tags=["responses"])
app.include_router(attachments_router, prefix="/api/v1/attachments", tags=["attachments"])
app.include_router(billing_router, prefix="/api/v1/billing", tags=["billing"])

install_enveloped_openapi(app)

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "SOIT API", "version": "1.0.0"}
