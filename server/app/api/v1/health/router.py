""" router

Health check and monitoring endpoints.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.ports.vector.interface import VectorPort
from app.wiring.container import get_container

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    """Status: 'healthy' or 'unhealthy'."""


class ReadyResponse(BaseModel):
    """Readiness check response."""

    status: str
    """Status: 'ready' or 'not_ready'."""

    database: str
    """Database status: 'connected' or 'disconnected'."""

    storage: str
    """Object storage status: 'connected' or 'disconnected'."""

    vector: str = "unknown"
    """Vector store status: 'connected' or 'unavailable' (reported, non-gating)."""


def get_readiness_storage() -> StoragePort:
    """Return the unscoped storage adapter used by readiness checks."""

    return get_container().get("storage_port")


def get_readiness_vector() -> VectorPort:
    """Return the unscoped vector adapter used by readiness checks."""

    return get_container().get("vector_port")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint.

    Returns:
        Health status.
    """
    return HealthResponse(status="healthy")


@router.get("/health/ready", response_model=ReadyResponse)
async def readiness_check(
    db: Session = Depends(get_db),
    storage: StoragePort = Depends(get_readiness_storage),
    vector: VectorPort = Depends(get_readiness_vector),
):
    """Readiness check endpoint.

    Database and object storage are hard readiness gates (503 when down). The vector
    store is probed and reported but does not gate readiness: the platform degrades
    gracefully when it is down (non-vector endpoints keep serving), so a vector
    outage is surfaced without pulling the instance out of rotation.

    Returns:
        Readiness status.
    """
    try:
        # Try to execute a simple query
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        )

    try:
        await storage.ensure_ready()
        storage_status = "connected"
    except Exception:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage is unavailable",
        )

    try:
        await vector.check_ready()
        vector_status = "connected"
    except Exception:
        vector_status = "unavailable"

    return ReadyResponse(
        status="ready",
        database=db_status,
        storage=storage_status,
        vector=vector_status,
    )


@router.get("/health/live", response_model=HealthResponse)
async def liveness_check():
    """Liveness check endpoint.

    Returns:
        Liveness status.
    """
    return HealthResponse(status="healthy")


@router.get("/metrics")
async def metrics(request: Request):
    """Prometheus metrics endpoint.

    When ``settings.metrics_token`` is set, a matching ``Authorization: Bearer``
    header is required (for Prometheus ``bearer_token`` scrape configs). When it is
    unset, the endpoint is open and must be protected at the network layer.

    Returns:
        Prometheus metrics in text format.
    """
    from fastapi import Response
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    from app.settings.settings import settings

    expected_token = getattr(settings, "metrics_token", None)
    if expected_token:
        auth_header = request.headers.get("Authorization", "")
        provided = auth_header[7:] if auth_header.startswith("Bearer ") else None
        if not provided or not secrets.compare_digest(provided, expected_token):
            return Response(status_code=http_status.HTTP_401_UNAUTHORIZED)

    metrics_output = generate_latest()

    return Response(
        content=metrics_output,
        media_type=CONTENT_TYPE_LATEST,
    )
