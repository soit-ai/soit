""" router

Health check and monitoring endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.kernel.db.session import get_db


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
        status = "ready"
    except Exception:
        db_status = "disconnected"
        status = "not_ready"
    
    return ReadyResponse(status=status, database=db_status)


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
    # TODO: Implement Prometheus metrics export
    # For now, return empty metrics
    return "# Prometheus metrics\n# TODO: Implement metrics collection\n"

