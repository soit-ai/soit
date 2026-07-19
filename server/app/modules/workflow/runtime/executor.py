""" executor

DAG execution engine for workflows.
"""

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import asdict
from typing import Any

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.runtime.db.models.runs import Run, RunStep
from app.modules.workflow.application.variable_resolver import VariableResolver
from app.modules.workflow.runtime.engine import ExecutionEngine
from app.modules.workflow.runtime.executors import get_executor
from app.modules.workflow.runtime.executors.base import ExecutionContext
from app.modules.workflow.runtime.workflow_outbox_emit import (
    enqueue_workflow_node_completed,
    enqueue_workflow_node_failed,
)


class WorkflowApprovalRequired(Exception):
    """Control signal that checkpoints a workflow before a governed tool call."""

    def __init__(
        self,
        *,
        node_id: str,
        run_step_id: str,
        output: dict[str, Any],
    ) -> None:
        self.node_id = node_id
        self.run_step_id = run_step_id
        self.output = output
        super().__init__(f"Workflow node {node_id} is waiting for approval")


def _emit_workflow_node_completed_outbox(
    context: ExecutionContext,
    *,
    node_id: str,
    run_step: RunStep,
    next_node_id: str | None = None,
) -> None:
    if not getattr(context, "workflow_run_id", None):
        return
    if run_step.step_type != "workflow_node":
        return
    wid = context.workflow_run_id
    assert wid is not None
    db = context.trace_writer.db
    enqueue_workflow_node_completed(
        db,
        context.ctx,
        workflow_run_id=wid,
        run_id=context.run_id,
        node_id=node_id,
        step_pk=run_step.id,
        next_node_id=next_node_id,
    )
    db.commit()


def _emit_workflow_node_failed_outbox(
    context: ExecutionContext,
    *,
    node_id: str,
    run_step: RunStep,
    error_code: str | None,
    error_message: str | None,
) -> None:
    if not getattr(context, "workflow_run_id", None):
        return
    if run_step.step_type != "workflow_node":
        return
    wid = context.workflow_run_id
    assert wid is not None
    db = context.trace_writer.db
    enqueue_workflow_node_failed(
        db,
        context.ctx,
        workflow_run_id=wid,
        run_id=context.run_id,
        node_id=node_id,
        step_pk=run_step.id,
        error_code=error_code,
        error_message=error_message,
    )
    db.commit()


class WorkflowExecutor:
    """DAG execution engine for workflows."""

    def __init__(self, execution_engine: ExecutionEngine):
        """Initialize workflow executor.

        Args:
            execution_engine: Execution engine instance.
        """
        self.execution_engine = execution_engine

    async def execute(
        self,
        plan: ExecutionPlan,
        context: ExecutionContext,
        *,
        checkpoint: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute workflow DAG.

        Args:
            plan: Execution plan.
            context: Execution context.

        Returns:
            Final output dictionary.
        """
        nodes = plan.plan_data["nodes"]
        edges = plan.plan_data["edges"]
        execution_order = plan.plan_data["execution_order"]
        semantics = plan.plan_data.get("semantics", {})
        policy = plan.plan_data.get("policy", {})
        context.workflow_inputs = dict(plan.inputs or {})
        context_payload = asdict(context.ctx) if context.ctx else {}

        # Build graph for dependency tracking
        edge_map = self._build_edge_map(edges)
        reverse_edge_map = self._build_reverse_edge_map(edges)

        checkpoint = checkpoint or {}
        restored_states = dict(checkpoint.get("node_states") or {})
        # Waiting nodes are re-entered; only terminal progress is restored.
        node_states: dict[str, str] = {
            str(node_id): str(status)
            for node_id, status in restored_states.items()
            if status in {"succeeded", "skipped"}
        }
        node_outputs: dict[str, dict[str, Any]] = {
            str(node_id): dict(output)
            for node_id, output in dict(checkpoint.get("node_outputs") or {}).items()
            if isinstance(output, dict)
        }
        resume_node_id = str(checkpoint.get("waiting_node_id") or "") or None
        resume_workflow_step_id = (
            str(checkpoint.get("workflow_run_step_id") or "") or None
        )
        in_degree = {node_id: len(reverse_edge_map.get(node_id, [])) for node_id in nodes}
        incoming_active = dict.fromkeys(nodes, 0)
        has_incoming = {node_id: in_degree[node_id] > 0 for node_id in nodes}

        # Execution queue (nodes ready to execute)
        ready_queue: deque[str] = deque()
        queued_nodes: set[str] = set()

        class CompensationRequested(Exception):
            def __init__(self, node_id: str, error_message: str):
                super().__init__(error_message)
                self.node_id = node_id
                self.error_message = error_message

        def _strip_control_keys(payload: dict[str, Any]) -> dict[str, Any]:
            if not payload:
                return {}
            cleaned = dict(payload)
            for key in ("__compensate", "__compensate_with", "__compensate_for"):
                cleaned.pop(key, None)
            return cleaned

        # Execute nodes in topological order with concurrency
        concurrency = semantics.get("concurrency", 1)
        semaphore = asyncio.Semaphore(concurrency)
        compensation_requested = False
        compensation_error: CompensationRequested | None = None
        approval_required: WorkflowApprovalRequired | None = None

        def resolve_edge_condition(condition: Any) -> bool:
            if condition is None:
                return True
            resolver = VariableResolver(plan.inputs, node_outputs)
            resolved = resolver.resolve(condition)
            return self._evaluate_condition(resolved, {})

        def mark_skipped(node_id: str) -> None:
            if node_states.get(node_id):
                return
            node_states[node_id] = "skipped"
            run_step = context.trace_writer.create_step(
                run_id=context.run_id,
                step_type="workflow_node",
                step_id=f"st_{node_id}",
                node_id=node_id,
            )
            context.trace_writer.update_step_status(
                run_step.id,
                status="skipped",
                output_summary="skipped",
                metrics={
                    "node_type": nodes[node_id]["type"],
                    "node_id": node_id,
                },
            )
            resolve_outgoing_edges(node_id, allow_edges=False)

        def resolve_outgoing_edges(node_id: str, allow_edges: bool) -> None:
            for edge in edge_map.get(node_id, []):
                to_id = edge["to"]
                if in_degree[to_id] <= 0:
                    continue
                in_degree[to_id] -= 1
                if allow_edges and resolve_edge_condition(edge.get("when")):
                    incoming_active[to_id] += 1
                if in_degree[to_id] == 0:
                    if node_states.get(to_id):
                        continue
                    if incoming_active[to_id] > 0 or not has_incoming[to_id]:
                        if to_id not in queued_nodes:
                            ready_queue.append(to_id)
                            queued_nodes.add(to_id)
                    else:
                        mark_skipped(to_id)

        for node_id, degree in in_degree.items():
            if degree == 0 and node_id not in node_states:
                ready_queue.append(node_id)
                queued_nodes.add(node_id)
        for node_id in execution_order:
            restored_status = node_states.get(node_id)
            if restored_status in {"succeeded", "skipped"}:
                resolve_outgoing_edges(
                    node_id,
                    allow_edges=restored_status == "succeeded",
                )

        async def execute_node(node_id: str):
            """Execute a single node."""
            async with semaphore:
                if node_states.get(node_id) == "skipped":
                    return
                node = nodes[node_id]
                node_type = node["type"]
                step_id_base = f"st_{node_id}"

                pause_wait_ms = 0
                wait_started = time.monotonic()
                await self._wait_for_resume(context.run_id, semantics)
                pause_wait_ms = int((time.monotonic() - wait_started) * 1000)

                # Get executor
                executor_class = get_executor(node_type)
                executor = executor_class()

                # Resolve inputs
                # Build steps_outputs mapping: node_id -> output
                steps_outputs_map = {}
                for nid in execution_order:
                    if nid in node_outputs:
                        steps_outputs_map[nid] = node_outputs[nid]

                skipped_steps = {nid for nid, state in node_states.items() if state == "skipped"}
                resolver = VariableResolver(
                    plan.inputs,
                    steps_outputs_map,
                    context=context_payload,
                    skipped_steps=skipped_steps,
                )
                inputs = _strip_control_keys(resolver.resolve(node.get("input", {})))

                def create_attempt_step(attempt: int):
                    """Create a run step for this attempt."""
                    if (
                        attempt == 1
                        and node_id == resume_node_id
                        and resume_workflow_step_id
                    ):
                        resumed_step = context.trace_writer.db.get(
                            RunStep,
                            resume_workflow_step_id,
                        )
                        if (
                            resumed_step is None
                            or resumed_step.run_id != context.run_id
                            or resumed_step.node_id != node_id
                            or resumed_step.status != "waiting_approval"
                        ):
                            raise ValidationError(
                                "Workflow approval checkpoint is not resumable"
                            )
                        return context.trace_writer.update_step_status(
                            resumed_step.id,
                            status="running",
                        )
                    step_key = step_id_base if attempt == 1 else f"{step_id_base}_retry{attempt}"
                    run_step = context.trace_writer.create_step(
                        run_id=context.run_id,
                        step_type="workflow_node",
                        step_id=step_key,
                        node_id=node_id,
                        input_summary=str(inputs)[:8192] if inputs else None,
                    )
                    context.trace_writer.update_step_status(
                        run_step.id,
                        status="running",
                    )
                    return run_step

                attempt = 1
                attempts = 0
                run_step = create_attempt_step(attempt)

                # Create step context after initial step is created.
                step_context = ExecutionContext(
                    run_id=context.run_id,
                    step_id=run_step.id,
                    ctx=context.ctx,
                    trace_writer=context.trace_writer,
                    llm_port=context.llm_port,
                    tool_port=context.tool_port,
                    vector_port=context.vector_port,
                    plugin_runtime_port=context.plugin_runtime_port,
                    response_service=context.response_service,
                    workflow_policy=context.workflow_policy,
                    workflow_inputs=context.workflow_inputs,
                    steps_outputs=node_outputs,
                    workflow_run_id=context.workflow_run_id,
                    approval_checkpoint_gateway=context.approval_checkpoint_gateway,
                    task_id=context.task_id,
                    thread_id=context.thread_id,
                    agent_id=context.agent_id,
                    resume_approval_node_id=resume_node_id,
                    resume_tool_call_id=checkpoint.get("tool_call_id"),
                    resume_tool_run_step_id=checkpoint.get("tool_run_step_id"),
                    resume_response_id=checkpoint.get("response_id"),
                )
                final_error_recorded = False
                try:
                    # Execute node with retry/timeout
                    retry_policy = node.get("retry_policy") or policy.get("default_retry_policy") or {}
                    max_retries = int(retry_policy.get("max_retries", 0) or 0)
                    backoff_ms = retry_policy.get("backoff_ms")
                    timeout_ms = node.get("timeout_ms") or policy.get("default_timeout_ms")

                    async def _run_once():
                        if timeout_ms:
                            return await asyncio.wait_for(
                                executor.execute(node, step_context, inputs),
                                timeout=timeout_ms / 1000,
                            )
                        return await executor.execute(node, step_context, inputs)

                    while True:
                        exec_started = time.monotonic()
                        try:
                            step_context.step_id = run_step.id
                            output = await _run_once()
                            if (
                                isinstance(output, dict)
                                and output.get("status") == "waiting_approval"
                            ):
                                raise WorkflowApprovalRequired(
                                    node_id=node_id,
                                    run_step_id=run_step.id,
                                    output=output,
                                )
                            break
                        except WorkflowApprovalRequired:
                            raise
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            attempts += 1
                            elapsed_ms = int((time.monotonic() - exec_started) * 1000)
                            context.trace_writer.update_step_status(
                                run_step.id,
                                status="failed",
                                output_summary=str(exc)[:8192],
                                error_code="NODE_EXECUTION_ERROR",
                                error_message=str(exc),
                                error_details={
                                    "node_id": node_id,
                                    "node_type": node_type,
                                    "attempt": attempt,
                                    "error_type": type(exc).__name__,
                                },
                                metrics={
                                    "attempt": attempt,
                                    "node_type": node_type,
                                    "node_id": node_id,
                                    "latency_ms": elapsed_ms,
                                    "pause_wait_ms": pause_wait_ms,
                                    "max_retries": max_retries,
                                },
                            )
                            if attempts > max_retries:
                                final_error_recorded = True
                                raise
                            if backoff_ms:
                                await asyncio.sleep(backoff_ms / 1000)
                            attempt += 1
                            run_step = create_attempt_step(attempt)

                    node_outputs[node_id] = output
                    node_states[node_id] = "succeeded"

                    # Update step status to succeeded
                    elapsed_ms = int((time.monotonic() - exec_started) * 1000)
                    metrics = {
                        "attempts": attempt,
                        "node_type": node_type,
                        "node_id": node_id,
                        "latency_ms": elapsed_ms,
                        "pause_wait_ms": pause_wait_ms,
                        "max_retries": max_retries,
                    }
                    if timeout_ms is not None:
                        metrics["timeout_ms"] = int(timeout_ms)
                    run_step = context.trace_writer.update_step_status(
                        run_step.id,
                        status="succeeded",
                        output_summary=str(output)[:8192] if output else None,
                        metrics=metrics,
                    )
                    _emit_workflow_node_completed_outbox(context, node_id=node_id, run_step=run_step)

                    resolve_outgoing_edges(node_id, allow_edges=True)

                except WorkflowApprovalRequired:
                    node_states[node_id] = "waiting_approval"
                    context.trace_writer.update_step_status(
                        run_step.id,
                        status="waiting_approval",
                        output_summary="waiting_approval",
                        metrics={
                            "attempts": attempt,
                            "node_type": node_type,
                            "node_id": node_id,
                            "max_retries": max_retries,
                        },
                    )
                    raise
                except asyncio.CancelledError:
                    node_states[node_id] = "canceled"
                    elapsed_ms = int((time.monotonic() - exec_started) * 1000)
                    context.trace_writer.update_step_status(
                        run_step.id,
                        status="canceled",
                        output_summary="canceled",
                        metrics={
                            "attempts": attempt,
                            "node_type": node_type,
                            "node_id": node_id,
                            "latency_ms": elapsed_ms,
                            "pause_wait_ms": pause_wait_ms,
                            "max_retries": max_retries,
                        },
                        error_code="NODE_CANCELED",
                        error_message="Node execution canceled",
                    )
                    raise
                except Exception as e:
                    node_states[node_id] = "failed"

                    # Update step status to failed
                    error_message = str(e)
                    elapsed_ms = int((time.monotonic() - exec_started) * 1000)
                    if not final_error_recorded:
                        metrics = {
                            "node_type": node_type,
                            "node_id": node_id,
                            "attempts": attempt,
                            "latency_ms": elapsed_ms,
                            "pause_wait_ms": pause_wait_ms,
                            "max_retries": max_retries,
                        }
                        if timeout_ms is not None:
                            metrics["timeout_ms"] = int(timeout_ms)
                        run_step = context.trace_writer.update_step_status(
                            run_step.id,
                            status="failed",
                            output_summary=error_message[:8192],
                            error_code="NODE_EXECUTION_ERROR",
                            error_message=error_message,
                            error_details={
                                "node_id": node_id,
                                "node_type": node_type,
                                "attempts": attempts + 1,
                                "error_type": type(e).__name__,
                            },
                            metrics=metrics,
                        )

                    _emit_workflow_node_failed_outbox(
                        context,
                        node_id=node_id,
                        run_step=run_step,
                        error_code="NODE_EXECUTION_ERROR",
                        error_message=error_message[:8192],
                    )

                    error_strategy = semantics.get("on_error", "fail_fast")

                    if error_strategy == "fail_fast":
                        raise ValidationError(f"Node {node_id} failed: {error_message}")
                    elif error_strategy == "continue":
                        # Continue execution, mark node as failed
                        node_outputs[node_id] = {"error": error_message}
                        resolve_outgoing_edges(node_id, allow_edges=True)
                    elif error_strategy == "compensate":
                        raise CompensationRequested(node_id=node_id, error_message=error_message)
                    # other strategies: ignore

        def _collect_compensation_nodes() -> list[str]:
            compensation_nodes: list[str] = []
            seen: set[str] = set()
            for node_id in reversed(execution_order):
                if node_states.get(node_id) != "succeeded":
                    continue
                node = nodes.get(node_id, {})
                inputs = node.get("input", {}) or {}
                refs = inputs.get("__compensate_with") or inputs.get("__compensate") or []
                if isinstance(refs, str):
                    refs = [refs]
                if not isinstance(refs, list):
                    continue
                for ref in refs:
                    if isinstance(ref, str) and ref in nodes and ref not in seen:
                        compensation_nodes.append(ref)
                        seen.add(ref)
            return compensation_nodes

        async def _execute_compensation_nodes() -> None:
            compensation_nodes = _collect_compensation_nodes()
            for comp_node_id in compensation_nodes:
                node = nodes.get(comp_node_id)
                if not node:
                    continue
                node_type = node["type"]
                executor_class = get_executor(node_type)
                executor = executor_class()
                inputs = _strip_control_keys(
                    VariableResolver(
                        plan.inputs,
                        node_outputs,
                        context=context_payload,
                        skipped_steps={nid for nid, state in node_states.items() if state == "skipped"},
                    ).resolve(node.get("input", {}))
                )
                run_step = context.trace_writer.create_step(
                    run_id=context.run_id,
                    step_type="workflow_compensate",
                    step_id=f"st_comp_{comp_node_id}",
                    node_id=comp_node_id,
                    input_summary=str(inputs)[:8192] if inputs else None,
                )
                context.trace_writer.update_step_status(run_step.id, status="running")
                step_context = ExecutionContext(
                    run_id=context.run_id,
                    step_id=run_step.id,
                    ctx=context.ctx,
                    trace_writer=context.trace_writer,
                    llm_port=context.llm_port,
                    tool_port=context.tool_port,
                    vector_port=context.vector_port,
                    plugin_runtime_port=context.plugin_runtime_port,
                    response_service=context.response_service,
                    workflow_policy=context.workflow_policy,
                    workflow_inputs=context.workflow_inputs,
                    steps_outputs=node_outputs,
                    workflow_run_id=context.workflow_run_id,
                    approval_checkpoint_gateway=context.approval_checkpoint_gateway,
                    task_id=context.task_id,
                    thread_id=context.thread_id,
                    agent_id=context.agent_id,
                )
                try:
                    output = await executor.execute(node, step_context, inputs)
                    node_outputs[comp_node_id] = output
                    context.trace_writer.update_step_status(
                        run_step.id,
                        status="succeeded",
                        output_summary=str(output)[:8192] if output else None,
                        metrics={
                            "node_type": node_type,
                            "node_id": comp_node_id,
                            "compensate": True,
                        },
                    )
                except Exception as exc:
                    context.trace_writer.update_step_status(
                        run_step.id,
                        status="failed",
                        output_summary=str(exc)[:8192],
                        error_code="NODE_COMPENSATION_ERROR",
                        error_message=str(exc),
                        error_details={
                            "node_id": comp_node_id,
                            "node_type": node_type,
                        },
                        metrics={
                            "node_type": node_type,
                            "node_id": comp_node_id,
                            "compensate": True,
                        },
                    )

        # Execute all nodes
        tasks = []
        while ready_queue or tasks:
            # Start new tasks for ready nodes
            while ready_queue and len(tasks) < concurrency:
                node_id = ready_queue.popleft()
                queued_nodes.discard(node_id)
                tasks.append(asyncio.create_task(execute_node(node_id)))

            # Wait for at least one task to complete
            if tasks:
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                tasks = list(pending)

                # Check for exceptions
                for task in done:
                    try:
                        await task
                    except WorkflowApprovalRequired as exc:
                        approval_required = exc
                        for pending_task in tasks:
                            pending_task.cancel()
                        for pending_task in tasks:
                            try:
                                await pending_task
                            except asyncio.CancelledError:
                                pass
                            except Exception:
                                pass
                        tasks = []
                        break
                    except CompensationRequested as exc:
                        compensation_requested = True
                        compensation_error = exc
                        for pending_task in tasks:
                            pending_task.cancel()
                        for pending_task in tasks:
                            try:
                                await pending_task
                            except Exception:
                                pass
                        tasks = []
                        break
                    except Exception:
                        # If fail_fast, propagate exception
                        if semantics.get("on_error", "fail_fast") == "fail_fast":
                            raise
                        # Otherwise, continue

            if compensation_requested or approval_required:
                break

        if approval_required:
            approval_output = dict(approval_required.output)
            approval_output["_checkpoint"] = {
                "inputs": plan.inputs,
                "node_states": {
                    node_id: status
                    for node_id, status in node_states.items()
                    if status in {"succeeded", "skipped"}
                },
                "node_outputs": {
                    node_id: output
                    for node_id, output in node_outputs.items()
                    if node_states.get(node_id) == "succeeded"
                },
                "waiting_node_id": approval_required.node_id,
                "workflow_run_step_id": approval_required.run_step_id,
                "tool_call_id": approval_output.get("tool_call_id"),
                "tool_run_step_id": approval_output.get("tool_run_step_id"),
                "response_id": approval_output.get("response_id"),
            }
            return approval_output

        if compensation_requested:
            await _execute_compensation_nodes()
            error_message = compensation_error.error_message if compensation_error else "Compensation triggered"
            raise ValidationError(f"Workflow compensated after failure: {error_message}")

        output_node_ids = [node_id for node_id, node in nodes.items() if node["type"] == "output"]
        if output_node_ids:
            active_output_node_ids = [
                node_id
                for node_id in output_node_ids
                if node_states.get(node_id) == "succeeded" and node_id in node_outputs
            ]
            if len(active_output_node_ids) != 1:
                raise ValidationError("Workflow must produce exactly one active output")
            return node_outputs[active_output_node_ids[0]]

        # If no output node, return last node's output
        if execution_order and execution_order[-1] in node_outputs:
            return node_outputs[execution_order[-1]]

        return {}

    async def _wait_for_resume(self, run_id: str, semantics: dict[str, Any]) -> None:
        """Block execution while run is paused."""
        poll_ms = semantics.get("pause_poll_ms", 500)
        while True:
            run = self.execution_engine.db.get(Run, run_id)
            status = getattr(run, "status", None)
            if status == "paused":
                await asyncio.sleep(poll_ms / 1000)
                continue
            if status == "canceled":
                raise asyncio.CancelledError()
            return

    def _build_graph(self, edges: list[dict[str, str]]) -> dict[str, list[str]]:
        """Build forward graph (from -> to)."""
        graph = defaultdict(list)
        for edge in edges:
            graph[edge["from"]].append(edge["to"])
        return dict(graph)

    def _build_reverse_graph(self, edges: list[dict[str, str]]) -> dict[str, list[str]]:
        """Build reverse graph (to -> from)."""
        graph = defaultdict(list)
        for edge in edges:
            graph[edge["to"]].append(edge["from"])
        return dict(graph)

    def _build_edge_map(self, edges: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Build forward edge map (from -> edges)."""
        graph = defaultdict(list)
        for edge in edges:
            graph[edge["from"]].append(edge)
        return dict(graph)

    def _build_reverse_edge_map(self, edges: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Build reverse edge map (to -> edges)."""
        graph = defaultdict(list)
        for edge in edges:
            graph[edge["to"]].append(edge)
        return dict(graph)

    def _evaluate_condition(self, condition: Any, inputs: dict[str, Any]) -> bool:
        """Evaluate condition expression for edge routing."""
        if isinstance(condition, bool):
            return condition
        if isinstance(condition, int | float):
            return bool(condition)
        if isinstance(condition, str):
            trimmed = condition.strip()
            if trimmed.lower() in ("true", "false"):
                return trimmed.lower() == "true"
            if "==" in trimmed:
                parts = trimmed.split("==", 1)
                left = self._get_condition_value(parts[0].strip(), inputs)
                right = self._get_condition_value(parts[1].strip(), inputs)
                return left == right
            if "!=" in trimmed:
                parts = trimmed.split("!=", 1)
                left = self._get_condition_value(parts[0].strip(), inputs)
                right = self._get_condition_value(parts[1].strip(), inputs)
                return left != right
            if ">" in trimmed:
                parts = trimmed.split(">", 1)
                left = self._get_condition_value(parts[0].strip(), inputs)
                right = self._get_condition_value(parts[1].strip(), inputs)
                return float(left) > float(right)
            if "<" in trimmed:
                parts = trimmed.split("<", 1)
                left = self._get_condition_value(parts[0].strip(), inputs)
                right = self._get_condition_value(parts[1].strip(), inputs)
                return float(left) < float(right)
            value = self._get_condition_value(trimmed, inputs)
            return bool(value)
        return bool(condition)

    def _get_condition_value(self, expr: str, inputs: dict[str, Any]) -> Any:
        raw_expr = expr.strip()
        is_quoted = (
            len(raw_expr) >= 2
            and raw_expr[0] == raw_expr[-1]
            and raw_expr[0] in ('"', "'")
        )
        expr = raw_expr.strip('"').strip("'")
        if expr in inputs:
            return inputs[expr]
        normalized = expr.lower()
        if not is_quoted and normalized in ("true", "false"):
            return normalized == "true"
        try:
            if "." in expr:
                return float(expr)
            return int(expr)
        except ValueError:
            return expr
