"""agent_executor

Agent runtime executor for agent.v1 specs.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.commons.ids import generate_run_id
from app.kernel.events.bus import EventBus
from app.kernel.trace.writer import TraceWriter
from app.modules.workflow.runtime.engine import ExecutionEngine


class AgentExecutorV1:
    """Agent executor that reads runtime config from app_versions.spec_json."""

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

    def _normalize_model_ref(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        if value.startswith("model:"):
            return value
        if ":" in value:
            return f"model:{value}"
        return f"model:{value}"

    def _resolve_model_ref(self, spec: Dict[str, Any], inputs: Dict[str, Any]) -> Optional[str]:
        if inputs.get("model"):
            return self._normalize_model_ref(inputs.get("model"))
        if inputs.get("model_ref"):
            return self._normalize_model_ref(inputs.get("model_ref"))

        model_ref = spec.get("model_ref")
        model = spec.get("model")
        if not model_ref:
            if isinstance(model, str):
                model_ref = model
            elif isinstance(model, dict):
                model_ref = model.get("ref_key")
                if not model_ref:
                    provider = model.get("provider")
                    model_name = model.get("model")
                    if provider and model_name:
                        model_ref = f"model:{provider}:{model_name}"
        return self._normalize_model_ref(model_ref) if model_ref else None

    async def execute(
        self,
        *,
        app: Any,
        version: Any,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        spec = version.spec_json or {}
        merged_inputs = dict(inputs or {})

        model_ref = self._resolve_model_ref(spec, merged_inputs)
        if model_ref:
            merged_inputs["model"] = model_ref

        if "temperature" not in merged_inputs:
            model_params = (spec.get("model") or {}).get("params") if isinstance(spec.get("model"), dict) else {}
            if model_params and model_params.get("temperature") is not None:
                merged_inputs["temperature"] = model_params.get("temperature")

        limits = spec.get("limits") or {}
        if "max_iterations" not in merged_inputs and limits.get("max_iterations") is not None:
            merged_inputs["max_iterations"] = limits.get("max_iterations")

        if "tools" not in merged_inputs:
            allowlist = (spec.get("tools") or {}).get("allowlist") or []
            if isinstance(allowlist, list):
                merged_inputs["tools"] = [{"ref": ref} for ref in allowlist if ref]

        plan = ExecutionPlan(
            mode="agent",
            inputs=merged_inputs,
            run_id=generate_run_id(),
        )
        plan.app_id = app.id
        plan.app_version_id = version.id
        trace_writer = TraceWriter(self.db, self.ctx, event_bus=self.event_bus)
        engine = ExecutionEngine(self.db, self.ctx, trace_writer=trace_writer)
        result = await engine.execute(plan)
        return {"run_id": plan.run_id, "output": result}
