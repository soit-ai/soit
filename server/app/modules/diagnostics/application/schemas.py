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


class DiagnosticsSnapshot(BaseModel):
    generated_at: datetime
    version: str
    environment: str
    overall_status: OverallDiagnosticStatus
    dependencies: list[DependencyDiagnostic]
    process: ProcessDiagnostic
    workspace: WorkspaceDiagnostic
