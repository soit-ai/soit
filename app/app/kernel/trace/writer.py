""" writer

Trace writer interface (DB + artifact storage).
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.kernel.trace.models import Run, RunStep, RunArtifact, RunCost
from app.kernel.contracts.context import RequestContext
from app.kernel.commons.ids import (
    generate_run_id,
    generate_step_id,
    generate_artifact_id,
)
from app.kernel.commons.time import utc_now
from app.kernel.observability.metrics import (
    run_count,
    run_duration,
    step_count,
    step_duration,
    tokens_total,
    cost_total,
    active_runs,
)


class TraceWriter:
    """Write trace data to database and object storage."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize trace writer.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        self.db = db
        self.ctx = ctx
    
    def create_run(
        self,
        mode: str,
        app_version_id: Optional[str] = None,
        input_summary: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Run:
        """Create a new run.
        
        Args:
            mode: Execution mode (chat/bot/workflow/agent).
            app_version_id: Optional app version ID.
            input_summary: Optional input summary (max 8KB).
            
        Returns:
            Created Run instance.
        """
        run = Run(
            id=run_id or generate_run_id(),
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            mode=mode,
            app_version_id=app_version_id,
            status="queued",
            input_summary=input_summary[:8192] if input_summary else None,
            started_at=utc_now(),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        
        # Update metrics
        run_count.labels(mode=mode, status="queued", tenant_id=self.ctx.tenant_id).inc()
        active_runs.labels(mode=mode, tenant_id=self.ctx.tenant_id).inc()
        
        return run
    
    def update_run_status(
        self,
        run_id: str,
        status: str,
        output_summary: Optional[str] = None,
    ) -> Run:
        """Update run status.
        
        Args:
            run_id: Run ID.
            status: New status.
            output_summary: Optional output summary (max 8KB).
            
        Returns:
            Updated Run instance.
        """
        run = self.db.get(Run, run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")
        
        # Verify scope
        if run.tenant_id != self.ctx.tenant_id or run.workspace_id != self.ctx.workspace_id:
            raise ValueError("Run scope mismatch")
        
        old_status = run.status
        run.status = status
        if output_summary:
            run.output_summary = output_summary[:8192]
        if status in ("succeeded", "failed", "canceled"):
            run.ended_at = utc_now()
            # Calculate duration
            if run.started_at:
                started_at = run.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                duration_seconds = (run.ended_at - started_at).total_seconds()
                run_duration.labels(mode=run.mode, tenant_id=self.ctx.tenant_id).observe(duration_seconds)
            # Decrement active runs
            active_runs.labels(mode=run.mode, tenant_id=self.ctx.tenant_id).dec()
        run.updated_at = utc_now()
        
        # Update metrics
        if old_status != status:
            run_count.labels(mode=run.mode, status=status, tenant_id=self.ctx.tenant_id).inc()
        
        self.db.commit()
        self.db.refresh(run)
        return run
    
    def create_step(
        self,
        run_id: str,
        step_type: str,
        step_id: Optional[str] = None,
        node_id: Optional[str] = None,
        input_summary: Optional[str] = None,
    ) -> RunStep:
        """Create a new step.
        
        Args:
            run_id: Run ID.
            step_type: Step type (llm/retrieve/tool/node/plan).
            step_id: Optional step ID (e.g., "st_node1" for workflow nodes).
            node_id: Optional node ID.
            input_summary: Optional input summary (max 8KB).
            
        Returns:
            Created RunStep instance.
        """
        step = RunStep(
            id=generate_step_id(),
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            run_id=run_id,
            step_id=step_id,
            step_type=step_type,
            node_id=node_id,
            status="queued",
            input_summary=input_summary[:8192] if input_summary else None,
            started_at=utc_now(),
        )
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)
        
        # Update metrics
        step_count.labels(step_type=step_type, status="queued", tenant_id=self.ctx.tenant_id).inc()
        
        return step
    
    def update_step_status(
        self,
        step_id: str,
        status: str,
        output_summary: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> RunStep:
        """Update step status.
        
        Args:
            step_id: Step ID.
            status: New status.
            output_summary: Optional output summary (max 8KB).
            metrics: Optional metrics dictionary.
            error_code: Optional error code.
            error_message: Optional error message.
            error_details: Optional error details.
            
        Returns:
            Updated RunStep instance.
        """
        step = self.db.get(RunStep, step_id)
        if not step:
            raise ValueError(f"Step not found: {step_id}")
        
        # Verify scope
        if step.tenant_id != self.ctx.tenant_id or step.workspace_id != self.ctx.workspace_id:
            raise ValueError("Step scope mismatch")
        
        old_status = step.status
        step.status = status
        if output_summary:
            step.output_summary = output_summary[:8192]
        if metrics:
            step.metrics_json = metrics
        if error_code:
            step.error_code = error_code
        if error_message:
            step.error_message = error_message
        if error_details:
            step.error_details = error_details
        if status in ("succeeded", "failed", "skipped", "canceled"):
            step.ended_at = utc_now()
            # Calculate duration
            if step.started_at:
                started_at = step.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                duration_seconds = (step.ended_at - started_at).total_seconds()
                step_duration.labels(step_type=step.step_type, tenant_id=self.ctx.tenant_id).observe(duration_seconds)
        
        # Update metrics
        if old_status != status:
            step_count.labels(step_type=step.step_type, status=status, tenant_id=self.ctx.tenant_id).inc()
        
        self.db.commit()
        self.db.refresh(step)
        return step
    
    def create_artifact(
        self,
        run_id: str,
        artifact_type: str,
        storage_key: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> RunArtifact:
        """Create a new artifact.
        
        Args:
            run_id: Run ID.
            artifact_type: Artifact type (file/log/blob/json).
            storage_key: Storage key (object storage path).
            meta: Optional metadata (mime, size, hash, etc.).
            
        Returns:
            Created RunArtifact instance.
        """
        artifact = RunArtifact(
            id=generate_artifact_id(),
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            run_id=run_id,
            type=artifact_type,
            storage_key=storage_key,
            meta_json=meta,
        )
        self.db.add(artifact)
        self.db.commit()
        self.db.refresh(artifact)
        return artifact
    
    def update_cost(
        self,
        run_id: str,
        tokens_prompt: int = 0,
        tokens_completion: int = 0,
        embedding_count: int = 0,
        rerank_count: int = 0,
        ms_total: int = 0,
        storage_bytes: int = 0,
    ) -> RunCost:
        """Update or create run cost.
        
        Args:
            run_id: Run ID.
            tokens_prompt: Prompt tokens to add.
            tokens_completion: Completion tokens to add.
            embedding_count: Embedding count to add.
            rerank_count: Rerank count to add.
            ms_total: Milliseconds to add.
            storage_bytes: Storage bytes to add.
            
        Returns:
            Updated RunCost instance.
        """
        cost = self.db.get(RunCost, run_id)
        if cost:
            # Verify scope
            if cost.tenant_id != self.ctx.tenant_id or cost.workspace_id != self.ctx.workspace_id:
                raise ValueError("Cost scope mismatch")
            # Add to existing
            cost.tokens_prompt += tokens_prompt
            cost.tokens_completion += tokens_completion
            cost.embedding_count += embedding_count
            cost.rerank_count += rerank_count
            cost.ms_total += ms_total
            cost.storage_bytes += storage_bytes
            cost.updated_at = utc_now()
        else:
            # Create new
            cost = RunCost(
                run_id=run_id,
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                tokens_prompt=tokens_prompt,
                tokens_completion=tokens_completion,
                embedding_count=embedding_count,
                rerank_count=rerank_count,
                ms_total=ms_total,
                storage_bytes=storage_bytes,
            )
            self.db.add(cost)
        
        # Update metrics
        if tokens_prompt > 0:
            tokens_total.labels(type="prompt", tenant_id=self.ctx.tenant_id).inc(tokens_prompt)
        if tokens_completion > 0:
            tokens_total.labels(type="completion", tenant_id=self.ctx.tenant_id).inc(tokens_completion)
        if embedding_count > 0:
            tokens_total.labels(type="embedding", tenant_id=self.ctx.tenant_id).inc(embedding_count)
        
        self.db.commit()
        self.db.refresh(cost)
        return cost
