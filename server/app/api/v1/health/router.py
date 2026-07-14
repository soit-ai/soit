""" router

Health check and monitoring endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infra.db.session import get_db

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


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint.

    Returns:
        Health status.
    """
    return HealthResponse(status="healthy")


@router.get("/health/ready", response_model=ReadyResponse)
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness check endpoint (checks database connection).

    Args:
        db: Database session.

    Returns:
        Readiness status.
    """
    try:
        # Try to execute a simple query
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_status = "connected"
        readiness_status = "ready"
    except Exception:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        )

    return ReadyResponse(status=readiness_status, database=db_status)


@router.get("/health/live", response_model=HealthResponse)
async def liveness_check():
    """Liveness check endpoint.

    Returns:
        Liveness status.
    """
    return HealthResponse(status="healthy")


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint.

    Returns:
        Prometheus metrics in text format.
    """
    from fastapi import Response
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    # Generate Prometheus metrics
    metrics_output = generate_latest()

    return Response(
        content=metrics_output,
        media_type=CONTENT_TYPE_LATEST,
    )
