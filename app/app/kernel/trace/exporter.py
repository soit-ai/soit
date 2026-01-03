""" exporter

Trace exporters to observability stack.
"""

from typing import Optional, Dict, Any
from datetime import datetime

from app.kernel.trace.models import Run, RunStep, RunArtifact, RunCost
from app.kernel.commons.time import to_iso8601


class OpenTelemetryExporter:
    """Export trace data to OpenTelemetry."""
    
    def __init__(self):
        """Initialize OpenTelemetry exporter."""
        # In production, initialize OpenTelemetry SDK here
        # For now, this is a placeholder
        pass
    
    def export_run(self, run: Run) -> None:
        """Export run to OpenTelemetry.
        
        Args:
            run: Run instance to export.
        """
        # Placeholder: In production, create OpenTelemetry span
        # from opentelemetry import trace
        # tracer = trace.get_tracer(__name__)
        # with tracer.start_as_current_span(f"run.{run.mode}") as span:
        #     span.set_attribute("run.id", run.id)
        #     span.set_attribute("run.status", run.status)
        #     span.set_attribute("run.mode", run.mode)
        pass
    
    def export_step(self, step: RunStep) -> None:
        """Export step to OpenTelemetry.
        
        Args:
            step: RunStep instance to export.
        """
        # Placeholder: In production, create OpenTelemetry span
        # from opentelemetry import trace
        # tracer = trace.get_tracer(__name__)
        # with tracer.start_as_current_span(f"step.{step.step_type}") as span:
        #     span.set_attribute("step.id", step.id)
        #     span.set_attribute("step.type", step.step_type)
        #     span.set_attribute("step.status", step.status)
        #     if step.metrics_json:
        #         for key, value in step.metrics_json.items():
        #             span.set_attribute(f"step.{key}", value)
        pass


def to_runtrace_spec(
    run: Run,
    steps: list[RunStep],
    artifacts: Optional[list[RunArtifact]] = None,
    cost: Optional[RunCost] = None,
) -> Dict[str, Any]:
    """Convert run/step/artifact/cost to RunTraceSpec format.
    
    Args:
        run: Run instance.
        steps: List of RunStep instances.
        artifacts: Optional list of RunArtifact instances.
        cost: Optional RunCost instance.
        
    Returns:
        Dictionary conforming to RunTraceSpec schema.
    """
    spec: Dict[str, Any] = {
        "run": {
            "run_id": run.id,
            "tenant_id": run.tenant_id,
            "workspace_id": run.workspace_id,
            "mode": run.mode,
            "status": run.status,
            "started_at": to_iso8601(run.started_at),
        },
        "steps": [
            {
                "step_id": step.id,
                "step_type": step.step_type,
                "status": step.status,
                "started_at": to_iso8601(step.started_at),
            }
            for step in steps
        ],
    }
    
    # Add optional fields
    if run.app_version_id:
        spec["run"]["app_version_id"] = run.app_version_id
    if run.input_summary:
        spec["run"]["input_summary"] = run.input_summary
    if run.output_summary:
        spec["run"]["output_summary"] = run.output_summary
    if run.ended_at:
        spec["run"]["ended_at"] = to_iso8601(run.ended_at)
    
    # Add step details
    for i, step in enumerate(steps):
        if step.node_id:
            spec["steps"][i]["node_id"] = step.node_id
        if step.input_summary:
            spec["steps"][i]["input_summary"] = step.input_summary
        if step.output_summary:
            spec["steps"][i]["output_summary"] = step.output_summary
        if step.metrics_json:
            spec["steps"][i]["metrics"] = step.metrics_json
        if step.ended_at:
            spec["steps"][i]["ended_at"] = to_iso8601(step.ended_at)
        if step.error_code:
            spec["steps"][i]["error"] = {
                "code": step.error_code,
                "message": step.error_message or "",
                "details": step.error_details or {},
            }
    
    # Add artifacts if provided
    if artifacts:
        spec["artifacts"] = [
            {
                "artifact_id": artifact.id,
                "type": artifact.type,
                "storage_key": artifact.storage_key,
                "meta": artifact.meta_json,
            }
            for artifact in artifacts
        ]
    
    # Add cost if provided
    if cost:
        spec["cost"] = {
            "tokens_prompt": cost.tokens_prompt,
            "tokens_completion": cost.tokens_completion,
            "embedding_count": cost.embedding_count,
            "rerank_count": cost.rerank_count,
            "ms_total": cost.ms_total,
            "storage_bytes": cost.storage_bytes,
        }
    
    return spec
