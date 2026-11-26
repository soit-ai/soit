""" engine

Execution engine core entry.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.ids import generate_run_id
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.execution.state_machine import RunStatus, StateMachine
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.workflow.runtime.approval import (
    APPROVAL_REJECTED,
    WorkflowApprovalDeclined,
)
from app.modules.workflow.runtime.limits import WorkflowLimitExceeded

if TYPE_CHECKING:
    from app.modules.workflow.application.contracts import WorkflowKnowledgeQueryPort


def _limit_error_code(exc: BaseException) -> str | None:
    """A run stopped by a declared limit records the limit as its error code."""

    if isinstance(exc, WorkflowApprovalDeclined):
        return APPROVAL_REJECTED
    return exc.reason if isinstance(exc, WorkflowLimitExceeded) else None


class ExecutionEngine:
    """Execution engine for compiled workflow plans."""

    def __init__(
        self,
        db: AsyncSession,
        ctx: RequestContext,
        trace_writer: TraceWriter,
        response_service: ResponseService | None = None,
        approval_checkpoint_gateway: Any | None = None,
        approval_ledger: Any | None = None,
        workflow_knowledge_query_port: WorkflowKnowledgeQueryPort | None = None,
        node_knowledge_query_port_factory: Callable[[AsyncSession], WorkflowKnowledgeQueryPort]
        | None = None,
    ):
        """Initialize execution engine.

        Args:
            db: Database session.
            ctx: Request context.
            trace_writer: Trace writer.
            node_knowledge_query_port_factory: Builds a knowledge query port on
                a node's own session; without it concurrent nodes share the
                engine's port (and its session) for knowledge queries.
        """
        self.db = db
        self.ctx = ctx
        self.trace_writer = trace_writer
        self.response_service = response_service
        self.approval_checkpoint_gateway = approval_checkpoint_gateway
        self.approval_ledger = approval_ledger
        self.workflow_knowledge_query_port = workflow_knowledge_query_port
        self.node_knowledge_query_port_factory = node_knowledge_query_port_factory
        self.state_machine = StateMachine()

    async def execute(self, plan: ExecutionPlan) -> dict[str, Any]:
        """Execute an execution plan.

        Args:
            plan: Execution plan.

        Returns:
            Execution result.
        """
        if not plan.run_id:
            plan.run_id = generate_run_id()
        if not (plan.subject_kind and plan.subject_id):
            raise ValueError("ExecutionPlan requires subject_kind and subject_id")

        # Create run (metrics are recorded in trace_writer)
        input_summary = None
        if plan.inputs is not None:
            input_summary = json.dumps(plan.inputs, ensure_ascii=True, default=str)[:8192]

        run = await self.trace_writer.create_run(
            mode=plan.mode,
            subject_kind=plan.subject_kind,
            subject_id=plan.subject_id,
            subject_version_id=plan.subject_version_id,
            input_summary=input_summary,
            run_id=plan.run_id,
        )

        # Transition to running
        self.state_machine.transition_run(run, RunStatus.RUNNING.value)
        await self.trace_writer.update_run_status(run.id, run.status)

        try:
            # Execute based on mode
            # Agents and chat run through their own services; the workflow
            # compiler only ever produces workflow plans.
            if plan.mode != "workflow":
                raise ValueError(f"Unsupported mode: {plan.mode}")
            result = await self._execute_workflow(plan)

            if (
                plan.mode == "workflow"
                and isinstance(result, dict)
                and result.get("status") == "waiting_approval"
            ):
                self.state_machine.transition_run(
                    run,
                    RunStatus.WAITING_APPROVAL.value,
                )
                await self.trace_writer.update_run_status(
                    run.id,
                    run.status,
                    output_summary="waiting_approval",
                )
                return result

            # Transition to succeeded (metrics are recorded in trace_writer)
            self.state_machine.transition_run(run, RunStatus.SUCCEEDED.value)
            await self.trace_writer.update_run_status(
                run.id,
                run.status,
                output_summary=str(result)[:8192] if result else None,
            )

            return result
        except asyncio.CancelledError:
            # Transition to canceled
            self.state_machine.transition_run(run, RunStatus.CANCELED.value)
            await self.trace_writer.update_run_status(run.id, run.status)
            raise
        except Exception as exc:
            # Transition to failed (metrics are recorded in trace_writer)
            error_message = str(exc)
            self.state_machine.transition_run(run, RunStatus.FAILED.value)
            await self.trace_writer.update_run_status(
                run.id,
                run.status,
                output_summary=error_message[:8192],
                error_code=_limit_error_code(exc),
            )
            raise

    async def resume_workflow(
        self,
        plan: ExecutionPlan,
        *,
        workflow_run_id: str,
        checkpoint: dict[str, Any],
        approval_status: str,
        resume_statuses: tuple[str, ...] = ("waiting_approval",),
    ) -> dict[str, Any]:
        """Resume one workflow from a durable approval checkpoint.

        ``approval_status`` is the decision on the call the run stopped for.
        Only ``approved`` lets the call run; any other ends its node as
        ``APPROVAL_REJECTED`` without calling the tool.
        """

        run = await self.db.get(Run, plan.run_id)
        if (
            run is None
            or run.tenant_id != self.ctx.tenant_id
            or run.workspace_id != self.ctx.workspace_id
            or run.status != RunStatus.WAITING_APPROVAL.value
        ):
            raise ValueError("Workflow run is not waiting for approval")
        self.state_machine.transition_run(run, RunStatus.RUNNING.value)
        await self.trace_writer.update_run_status(run.id, run.status)
        try:
            result = await self._execute_workflow(
                plan,
                workflow_run_id=workflow_run_id,
                checkpoint={**checkpoint, "approval_status": approval_status},
                resume_statuses=resume_statuses,
            )
            if result.get("status") == "waiting_approval":
                self.state_machine.transition_run(
                    run,
                    RunStatus.WAITING_APPROVAL.value,
                )
                await self.trace_writer.update_run_status(
                    run.id,
                    run.status,
                    output_summary="waiting_approval",
                )
                return result
            self.state_machine.transition_run(run, RunStatus.SUCCEEDED.value)
            await self.trace_writer.update_run_status(
                run.id,
                run.status,
                output_summary=str(result)[:8192] if result else None,
            )
            return result
        except Exception as exc:
            self.state_machine.transition_run(run, RunStatus.FAILED.value)
            await self.trace_writer.update_run_status(
                run.id,
                run.status,
                output_summary=str(exc)[:8192],
                error_code=_limit_error_code(exc),
            )
            raise

    async def redrive_workflow(
        self,
        plan: ExecutionPlan,
        *,
        workflow_run_id: str,
        checkpoint: dict[str, Any],
    ) -> dict[str, Any]:
        """Resume one failed workflow from its crash checkpoint.

        The caller must already have staged the redrive: the Run in
        ``retrying`` and the WorkflowRun claimed back to ``queued``. Staging
        is a guarded compare-and-set, so two operators cannot redrive the
        same run twice.
        """

        run = await self.db.get(Run, plan.run_id)
        if (
            run is None
            or run.tenant_id != self.ctx.tenant_id
            or run.workspace_id != self.ctx.workspace_id
            or run.status != RunStatus.RETRYING.value
        ):
            raise ValueError("Workflow run is not staged for redrive")
        self.state_machine.transition_run(run, RunStatus.RUNNING.value)
        await self.trace_writer.update_run_status(run.id, run.status)
        try:
            result = await self._execute_workflow(
                plan,
                workflow_run_id=workflow_run_id,
                checkpoint=checkpoint,
                resume_statuses=("queued",),
            )
            if result.get("status") == "waiting_approval":
                self.state_machine.transition_run(
                    run,
                    RunStatus.WAITING_APPROVAL.value,
                )
                await self.trace_writer.update_run_status(
                    run.id,
                    run.status,
                    output_summary="waiting_approval",
                )
                return result
            self.state_machine.transition_run(run, RunStatus.SUCCEEDED.value)
            await self.trace_writer.update_run_status(
                run.id,
                run.status,
                output_summary=str(result)[:8192] if result else None,
            )
            return result
        except Exception as exc:
            self.state_machine.transition_run(run, RunStatus.FAILED.value)
            await self.trace_writer.update_run_status(
                run.id,
                run.status,
                output_summary=str(exc)[:8192],
                error_code=_limit_error_code(exc),
            )
            raise

    async def _execute_workflow(
        self,
        plan: ExecutionPlan,
        *,
        workflow_run_id: str | None = None,
        checkpoint: dict[str, Any] | None = None,
        resume_statuses: tuple[str, ...] = ("waiting_approval",),
    ) -> dict[str, Any]:
        """Execute workflow mode.

        Args:
            plan: Execution plan.

        Returns:
            Workflow result.
        """
        from app.modules.workflow.domain.models import WorkflowRun
        from app.modules.workflow.runtime.executor import WorkflowExecutor
        from app.modules.workflow.runtime.executors.base import ExecutionContext
        from app.wiring import get_container

        nodes_dict = plan.plan_data.get("nodes") or {}
        total_nodes = len(nodes_dict)
        if workflow_run_id:
            workflow_run_row = await self.db.get(WorkflowRun, workflow_run_id)
            if (
                workflow_run_row is None
                or workflow_run_row.tenant_id != self.ctx.tenant_id
                or workflow_run_row.workspace_id != self.ctx.workspace_id
                or workflow_run_row.run_id != plan.run_id
                or workflow_run_row.status not in resume_statuses
            ):
                raise ValueError("Workflow checkpoint is not resumable")
            workflow_run_row.status = "running"
            workflow_run_row.updated_at = utc_now()
            self.db.add(workflow_run_row)
            await self.db.flush()
        else:
            from sqlalchemy import select as sa_select

            # A streaming endpoint claims the WorkflowRun (with its lease and
            # input snapshot) before execution starts. Adopt that row instead
            # of creating a duplicate aggregate for the same run.
            claimed = (
                (await self.db.execute(
                    sa_select(WorkflowRun).where(
                        WorkflowRun.tenant_id == self.ctx.tenant_id,
                        WorkflowRun.workspace_id == self.ctx.workspace_id,
                        WorkflowRun.run_id == plan.run_id,
                        WorkflowRun.status.in_(("queued", "running")),
                    )
                ))
                .scalars()
                .first()
            )
            if claimed is not None:
                claimed.status = "running"
                claimed.total_nodes = total_nodes
                claimed.completed_nodes = 0
                claimed.failed_nodes = 0
                claimed.waiting_nodes = total_nodes
                claimed.updated_at = utc_now()
                self.db.add(claimed)
                await self.db.flush()
                workflow_run_row = claimed
            else:
                workflow_run_row = WorkflowRun(
                    tenant_id=self.ctx.tenant_id,
                    workspace_id=self.ctx.workspace_id,
                    run_id=plan.run_id,
                    workflow_id=plan.subject_id,
                    total_nodes=total_nodes,
                    completed_nodes=0,
                    failed_nodes=0,
                    waiting_nodes=total_nodes,
                    status="running",
                    # Who started it: a run that stops for approval is
                    # continued on the server as this member.
                    request_context_json=self.ctx.to_json(),
                )
                self.db.add(workflow_run_row)
                await self.db.flush()
            workflow_run_id = workflow_run_row.id

        # Get ports from container
        container = get_container()
        llm_port = container.get_llm_port(
            ctx=self.ctx,
            trace_writer=self.trace_writer,
        )
        tool_port = container.get_tool_port(
            ctx=self.ctx,
            trace_writer=self.trace_writer,
        )
        vector_port = container.get_vector_port(
            ctx=self.ctx,
            trace_writer=self.trace_writer,
        )
        plugin_runtime_port = container.get_plugin_runtime_port(
            ctx=self.ctx,
            trace_writer=self.trace_writer,
        )

        # Initialize workflow executor
        workflow_executor = WorkflowExecutor(self)

        async def build_node_context() -> ExecutionContext:
            """A context on its own session, so nodes can run concurrently.

            Everything that writes (trace writer, the ports that record cost,
            the response service) is rebuilt on the node session; the
            executor commits and closes it when the node finishes.
            """
            session = AsyncSession(bind=self.db.bind, expire_on_commit=False)
            writer = TraceWriter(
                session,
                self.ctx,
                event_bus=self.trace_writer.event_bus,
                sandbox=self.trace_writer.sandbox,
            )
            response_service = None
            if self.response_service is not None:
                response_service = ResponseService(
                    db=session,
                    ctx=self.ctx,
                    response_repo=ResponseRepository(session, self.ctx),
                    event_repo=ResponseEventRepository(session, self.ctx),
                    trace_writer=writer,
                )
            knowledge_port = self.workflow_knowledge_query_port
            if self.node_knowledge_query_port_factory is not None:
                knowledge_port = self.node_knowledge_query_port_factory(session)
            return ExecutionContext(
                run_id=plan.run_id,
                step_id=None,
                ctx=self.ctx,
                trace_writer=writer,
                llm_port=container.get_llm_port(ctx=self.ctx, trace_writer=writer),
                tool_port=container.get_tool_port(ctx=self.ctx, trace_writer=writer),
                vector_port=container.get_vector_port(ctx=self.ctx, trace_writer=writer),
                workflow_knowledge_query_port=knowledge_port,
                plugin_runtime_port=container.get_plugin_runtime_port(
                    ctx=self.ctx, trace_writer=writer
                ),
                response_service=response_service,
                workflow_policy=plan.plan_data.get("policy", {}),
                workflow_run_id=workflow_run_id,
                approval_checkpoint_gateway=self.approval_checkpoint_gateway,
                approval_ledger=self.approval_ledger,
                owned_session=session,
            )

        # Create execution context
        context = ExecutionContext(
            run_id=plan.run_id,
            step_id=None,
            ctx=self.ctx,
            trace_writer=self.trace_writer,
            llm_port=llm_port,
            tool_port=tool_port,
            vector_port=vector_port,
            workflow_knowledge_query_port=self.workflow_knowledge_query_port,
            plugin_runtime_port=plugin_runtime_port,
            response_service=self.response_service,
            workflow_policy=plan.plan_data.get("policy", {}),
            workflow_run_id=workflow_run_id,
            approval_checkpoint_gateway=self.approval_checkpoint_gateway,
            approval_ledger=self.approval_ledger,
            node_context_factory=build_node_context,
        )

        try:
            result = await workflow_executor.execute(
                plan,
                context,
                checkpoint=checkpoint,
            )
        except Exception:
            row = await self.db.get(WorkflowRun, workflow_run_id)
            if row is not None:
                row.status = "failed"
                # The execution attempt is over; a terminal row must never
                # look like live leased work.
                row.lease_owner = None
                row.lease_expires_at = None
                row.updated_at = utc_now()
                self.db.add(row)
            await self.db.commit()
            raise

        row = await self.db.get(WorkflowRun, workflow_run_id)
        if row is not None:
            if result.get("status") == "waiting_approval":
                row.status = "waiting_approval"
                row.checkpoint_json = dict(result.pop("_checkpoint"))
            else:
                row.status = "succeeded"
                row.checkpoint_json = None
            row.lease_owner = None
            row.lease_expires_at = None
            row.updated_at = utc_now()
            self.db.add(row)
        await self.db.commit()

        return result
