"""Real-time diagnostics schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

DiagnosticStatus = Literal["healthy", "unavailable"]
OverallDiagnosticStatus = Literal["healthy", "degraded"]


class DependencyDiagnostic(BaseModel):
    name: Literal["database", "object_storage"]
    status: DiagnosticStatus
    latency_ms: float
    message: str | None = None


class ProcessDiagnostic(BaseModel):
    uptime_seconds: int
    rss_bytes: int
    thread_count: int


class WorkspaceDiagnostic(BaseModel):
    agents: int | None = None
    workflows: int | None = None
    knowledge_bases: int | None = None
    plugins: int | None = None
    models: int | None = None
    threads: int | None = None
    active_runs: int | None = None
    failed_runs_24h: int | None = None
    open_feedback: int | None = None


class ExtensionDiagnostic(BaseModel):
    name: str
    status: Literal["mounted", "failed"]
    error: str | None = None


class EditionDiagnostic(BaseModel):
    edition: str
    license_status: Literal["absent", "active", "expired", "invalid"]
    license_id: str | None = None
    customer_id: str | None = None
    expires_at: datetime | None = None
    days_left: int | None = None
    reason: str | None = None
    """Why a configured license grants nothing."""
    enabled_features: list[str]
    ignored_entitlements: list[str] = []
    extensions: list[ExtensionDiagnostic] = []


class DiagnosticsSnapshot(BaseModel):
    generated_at: datetime
    version: str
    environment: str
    overall_status: OverallDiagnosticStatus
    dependencies: list[DependencyDiagnostic]
    process: ProcessDiagnostic
    workspace: WorkspaceDiagnostic
    edition: EditionDiagnostic
