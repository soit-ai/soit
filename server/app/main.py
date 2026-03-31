""" main

FastAPI application entry point.
"""

import sys
import asyncio
import os
from typing import Optional
from pathlib import Path

# Add project root to Python path
# This ensures 'app' module can be found when running main.py directly
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

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

from app.settings.settings import settings as app_settings
from app.kernel.commons.errors import KernelError
from app.kernel.observability.logging import setup_logging
from app.kernel.observability.sentry import setup_sentry
from app.kernel.observability.context import get_log_context
from app.infra.db.session import get_engine, create_tables
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.tracing import TracingMiddleware
from app.middleware.error_handler import ErrorHandlerMiddleware, ERROR_CODE_TO_STATUS
from app.middleware.response_envelope import ResponseEnvelopeMiddleware
from app.api.v1.schemas.response import error_envelope


# Setup logging
setup_logging()

# Setup Sentry
setup_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Startup
    # Create database tables if needed
    # create_tables()
    
    # Load installed plugins into runtime registry
    try:
        from app.modules.plugin.runtime.loader import PluginRuntimeLoader
        PluginRuntimeLoader().load_all()
    except Exception:
        # Best-effort; do not block app startup
        pass

    knowledge_worker_task = None
    if getattr(app_settings, "knowledge_ingest_worker_enabled", False):
        try:
            from app.modules.knowledge.runtime.ingest_worker import GlobalKnowledgeIngestWorker
            worker = GlobalKnowledgeIngestWorker()
            knowledge_worker_task = asyncio.create_task(
                worker.run_loop(
                    poll_interval=max(0.1, app_settings.knowledge_ingest_worker_poll_interval),
                    max_tasks=app_settings.knowledge_ingest_worker_max_tasks,
                    concurrency=app_settings.knowledge_ingest_worker_concurrency,
                )
            )
        except Exception:
            knowledge_worker_task = None

    outbox_worker_task = None
    try:
        from app.wiring.outbox_handlers import register_outbox_handlers

        register_outbox_handlers()
    except Exception:
        pass

    if getattr(app_settings, "outbox_dispatcher_enabled", False):
        try:
            from app.infra.db.session import get_db_sync
            from app.kernel.events.dispatcher import OutboxDispatcherService
            from app.wiring.outbox_handlers import get_outbox_registry

            _outbox_svc = OutboxDispatcherService(
                get_outbox_registry(),
                db_factory=get_db_sync,
                batch_limit=max(1, int(app_settings.outbox_dispatcher_batch_limit)),
                max_dispatch_attempts=max(1, int(app_settings.outbox_dispatcher_max_attempts)),
            )
            outbox_worker_task = asyncio.create_task(
                _outbox_svc.run_loop(
                    poll_interval_seconds=max(0.05, float(app_settings.outbox_dispatcher_poll_interval)),
                )
            )
        except Exception:
            outbox_worker_task = None

    yield
    
    # Shutdown
    # Cleanup resources if needed
    if knowledge_worker_task:
        knowledge_worker_task.cancel()
        try:
            await knowledge_worker_task
        except asyncio.CancelledError:
            pass

    if outbox_worker_task:
        outbox_worker_task.cancel()
        try:
            await outbox_worker_task
        except asyncio.CancelledError:
            pass


# Create FastAPI application
from app.docs.openapi import tags_metadata

app = FastAPI(
    title=getattr(app_settings, "PROJECT_NAME", "SOIT-Pro API"),
    description="SOIT-Pro LLM Development Platform API",
    version="1.0.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    tags_metadata=tags_metadata,
)

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
def _resolve_trace_ids(request: Request) -> tuple[Optional[str], Optional[str]]:
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
from app.api.v1.identity.router import router as identity_router
from app.api.v1.workflow.router import router as workflow_router
from app.api.v1.memory.router import router as memory_router
from app.api.v1.knowledge.router import router as knowledge_router
from app.api.v1.modelhub.router import router as modelhub_router
from app.api.v1.plugin.router import router as plugin_router
from app.api.v1.skill.router import router as skill_router
from app.api.v1.mcp.router import router as mcp_router
from app.api.v1.observability.router import router as observability_router
from app.api.v1.run.router import router as run_router
from app.api.v1.security.router import router as security_router
from app.api.v1.secrets.router import router as secrets_router
from app.api.v1.websocket.router import router as websocket_router
from app.api.v1.sse.router import router as sse_router
from app.api.v1.health.router import router as health_router
from app.api.v1.agent.router import router as agent_router
from app.api.v1.task.router import router as task_router
from app.api.v1.thread.router import router as thread_router
from app.api.v1.notification.router import router as notification_router
from app.api.v1.responses.router import router as responses_router
from app.api.v1.capabilities.router import router as capabilities_router

# Register routers
app.include_router(identity_router, prefix="/api/v1", tags=["identity"])
app.include_router(workflow_router, prefix="/api/v1/workflows", tags=["workflows"])
app.include_router(memory_router, prefix="/api/v1/memory", tags=["memory"])
app.include_router(knowledge_router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(modelhub_router, prefix="/api/v1/modelhub", tags=["modelhub"])
app.include_router(plugin_router, prefix="/api/v1/plugins", tags=["plugins"])
app.include_router(skill_router, prefix="/api/v1/skills", tags=["skills"])
app.include_router(mcp_router, prefix="/api/v1/mcp", tags=["mcp"])
app.include_router(observability_router, prefix="/api/v1/observability", tags=["observability"])
app.include_router(run_router, prefix="/api/v1/runs", tags=["runs"])
app.include_router(security_router, prefix="/api/v1/security", tags=["security"])
app.include_router(secrets_router, prefix="/api/v1/secrets", tags=["secrets"])
app.include_router(websocket_router, prefix="/api/v1", tags=["websocket"])
app.include_router(sse_router, prefix="/api/v1/sse", tags=["sse"])
app.include_router(health_router, tags=["health"])
app.include_router(agent_router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(task_router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(thread_router, prefix="/api/v1/threads", tags=["threads"])
app.include_router(notification_router, prefix="/api/v1/notifications", tags=["notifications"])
app.include_router(responses_router, prefix="/api/v1/responses", tags=["responses"])
app.include_router(capabilities_router, prefix="/api/v1/capabilities", tags=["capabilities"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "SOIT-Pro API", "version": "1.0.0"}
