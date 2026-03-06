"""workflow_executor

Workflow runtime executor for workflow.v1 specs.
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.ids import generate_run_id
from app.kernel.events.bus import EventBus
from app.kernel.trace.writer import TraceWriter
from app.modules.workflow.application.compiler import WorkflowCompiler
from app.modules.workflow.runtime.engine import ExecutionEngine


class WorkflowExecutorV1:
    """Workflow executor that compiles and executes workflow.v1 specs."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        *,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.event_bus = event_bus
        self.compiler = WorkflowCompiler()

    async def execute(
        self,
        *,
        app: Any,
        version: Any,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        plan = self.compiler.compile(version.spec_json, inputs, run_id=generate_run_id())
        plan.app_id = app.id
        plan.app_version_id = version.id
        plan.mode = "workflow"
        trace_writer = TraceWriter(self.db, self.ctx, event_bus=self.event_bus)
        engine = ExecutionEngine(self.db, self.ctx, trace_writer=trace_writer)
        result = await engine.execute(plan)
        return {"run_id": plan.run_id, "output": result}
