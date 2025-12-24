""" main

FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.kernel.config.settings import settings as app_settings
from app.kernel.commons.errors import KernelError
from app.kernel.observability.logging import setup_logging
from app.kernel.observability.sentry import setup_sentry
from app.kernel.observability.tracing import setup_tracing
from app.kernel.db.session import get_engine, create_tables
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.error_handler import ErrorHandlerMiddleware


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
    
    # Setup tracing
    setup_tracing(app)
    
    yield
    
    # Shutdown
    # Cleanup resources if needed


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

# Add middleware (order matters: first added is last executed)
app.add_middleware(ErrorHandlerMiddleware)
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


# Exception handlers are handled by ErrorHandlerMiddleware
# No need to register separate handlers


# Register routers
from app.modules.entrypoints.workflow.router import router as workflow_router
from app.modules.entrypoints.dataset.router import router as dataset_router
from app.modules.entrypoints.chat.router import router as chat_router
from app.modules.entrypoints.websocket.router import router as websocket_router
from app.modules.entrypoints.sse.router import router as sse_router
from app.modules.entrypoints.health.router import router as health_router

# Register routers
app.include_router(workflow_router, prefix="/api/v1/workflows", tags=["workflows"])
app.include_router(dataset_router, prefix="/api/v1/datasets", tags=["datasets"])
app.include_router(chat_router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(websocket_router, prefix="/api/v1", tags=["websocket"])
app.include_router(sse_router, prefix="/api/v1/sse", tags=["sse"])
app.include_router(health_router, tags=["health"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "SOIT-Pro API", "version": "1.0.0"}

