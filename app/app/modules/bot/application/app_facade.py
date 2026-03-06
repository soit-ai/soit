"""app_facade

Bot facade backed by unified apps/app_versions.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc, func

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.trace.writer import TraceWriter
from app.kernel.ports.llm.interface import LLMPort
from app.kernel.identity.guard import rbac_guard, workspace_guard
from app.kernel.identity.permissions import RESOURCE_BOT
from app.kernel.specs.validator import validate_runtime_spec
from app.modules.appcenter.domain.models import App, AppVersion
from app.modules.bot.application.schemas import BotCreate, BotUpdate, BotVersionCreate, BotVersionUpdate, BotExecuteRequest
from app.modules.appcenter.runtime.router import AppRuntimeRouter
from app.modules.appcenter.application.publish_service import AppPublishService
from app.kernel.trace.models import Run, RunStep, RunCostEntry, RunArtifact


class BotAppFacadeService:
    """Bot service backed by apps/app_versions."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        llm_port: Optional[LLMPort] = None,
        trace_writer: Optional[TraceWriter] = None,
        event_bus: Optional[Any] = None,
        publish_service: Optional[AppPublishService] = None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.llm_port = llm_port
        self.trace_writer = trace_writer
        self.runtime_router = AppRuntimeRouter(db, ctx, event_bus=event_bus)
        self.publish_service = publish_service or AppPublishService(db, ctx)

    def _resolve_bot_create_id(self, data: BotCreate, **kwargs) -> str:
        return data.name or f"new:{self.ctx.workspace_id}"

    def _get_bot_app(self, bot_id: str) -> App:
        app = self.db.get(App, bot_id)
        if not app or app.tenant_id != self.ctx.tenant_id or app.workspace_id != self.ctx.workspace_id:
            raise NotFoundError(f"Bot not found: {bot_id}")
        if app.type != "BOT":
            raise NotFoundError(f"Bot not found: {bot_id}")
        return app

    def _get_bot_version(self, bot_id: str, version_id: str) -> AppVersion:
        version = self.db.get(AppVersion, version_id)
        if (
            not version
            or version.app_id != bot_id
            or version.tenant_id != self.ctx.tenant_id
            or version.workspace_id != self.ctx.workspace_id
        ):
            raise NotFoundError(f"Version not found: {version_id}")
        return version

    def _next_version_number(self, app_id: str) -> int:
        query = select(func.max(AppVersion.version)).where(
            and_(
                AppVersion.app_id == app_id,
                AppVersion.tenant_id == self.ctx.tenant_id,
                AppVersion.workspace_id == self.ctx.workspace_id,
            )
        )
        max_val = self.db.exec(query).one()
        if hasattr(max_val, "_mapping"):
            max_val = max_val[0]
        elif isinstance(max_val, (list, tuple)):
            max_val = max_val[0] if max_val else None
        return int(max_val or 0) + 1

    def _build_spec(self, data: BotVersionCreate) -> Dict[str, Any]:
        metadata = dict(data.metadata_json or {})
        if data.version:
            metadata["display_version"] = data.version
        chat_spec = {
            "runtime": "chat_runtime_v1",
            "system_prompt": data.system_prompt,
            "model": {"ref_key": data.model_ref} if data.model_ref else None,
            "temperature": data.temperature,
            "max_tokens": data.max_tokens,
            "top_p": data.top_p,
            "tools": {
                "allowlist": data.tool_refs,
                "configs": None,
            },
        }
        return {
            "runtime": "bot_runtime_v1",
            "chat": chat_spec,
            "triggers": data.triggers,
            "channels": data.channels,
            "limits": data.limits or {
                "max_tokens": data.max_tokens,
                "timeout_ms": None,
                "budget": None,
            },
            "metadata": metadata or None,
        }

    def _merge_spec(self, spec: Dict[str, Any], data: BotVersionUpdate) -> Dict[str, Any]:
        next_spec = dict(spec or {})
        chat_spec = dict(next_spec.get("chat") or {})
        model = chat_spec.get("model")
        if not isinstance(model, dict):
            model = {"ref_key": None}

        if data.system_prompt is not None:
            chat_spec["system_prompt"] = data.system_prompt
        if data.model_ref is not None:
            model["ref_key"] = data.model_ref
            chat_spec["model"] = model
        if data.temperature is not None:
            chat_spec["temperature"] = data.temperature
        if data.max_tokens is not None:
            chat_spec["max_tokens"] = data.max_tokens
            limits = dict(next_spec.get("limits") or {})
            limits["max_tokens"] = data.max_tokens
            next_spec["limits"] = limits
        if data.top_p is not None:
            chat_spec["top_p"] = data.top_p
        if data.tool_refs is not None:
            chat_spec["tools"] = {
                "allowlist": data.tool_refs,
                "configs": (chat_spec.get("tools") or {}).get("configs"),
            }
        next_spec["chat"] = chat_spec

        if data.metadata_json is not None:
            next_spec["metadata"] = data.metadata_json
        if data.triggers is not None:
            next_spec["triggers"] = data.triggers
        if data.channels is not None:
            next_spec["channels"] = data.channels
        if data.limits is not None:
            next_spec["limits"] = data.limits
        return next_spec

    def _resolve_metrics_window(self, range_key: str) -> timedelta:
        mapping = {
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
            "90d": timedelta(days=90),
        }
        if range_key not in mapping:
            raise ValidationError(f"Unsupported range key: {range_key}")
        return mapping[range_key]

    @staticmethod
    def _unwrap_first_entity(row: Any) -> Any:
        if isinstance(row, tuple) or isinstance(row, list):
            return row[0] if row else None
        if hasattr(row, "_mapping"):
            values = list(row._mapping.values())
            return values[0] if values else None
        return row

    def _unwrap_entities(self, rows: List[Any]) -> List[Any]:
        return [entity for entity in (self._unwrap_first_entity(row) for row in rows) if entity is not None]

    @staticmethod
    def _build_trigger_message(trigger: str, event_payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        payload = event_payload or {}
        content = payload.get("message") or payload.get("content") or payload.get("text") or payload.get("query")
        if content is None:
            content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return {
            "role": "user",
            "content": f"[trigger:{trigger}] {content}",
            "metadata": {"trigger": trigger},
        }

    @staticmethod
    def _extract_message_count(input_summary: Optional[str]) -> int:
        if not input_summary:
            return 0
        try:
            payload = json.loads(input_summary)
            messages = payload.get("messages")
            if isinstance(messages, list):
                return len(messages)
        except Exception:
            return 0
        return 0

    def _resolve_execute_messages(self, data: BotExecuteRequest) -> List[Dict[str, Any]]:
        if data.messages:
            return [msg.model_dump() for msg in data.messages]
        return [self._build_trigger_message(data.trigger, data.event_payload)]

    def _resolve_trace_writer(self) -> TraceWriter:
        return self.trace_writer or TraceWriter(self.db, self.ctx)

    def _record_channel_deliveries(
        self,
        *,
        bot_id: str,
        run_id: Optional[str],
        version: AppVersion,
        output_text: str,
        trigger: str,
    ) -> None:
        if not run_id:
            return
        channels = (version.spec_json or {}).get("channels")
        if not isinstance(channels, dict) or not channels:
            return

        trace_writer = self._resolve_trace_writer()
        for channel_name, config in channels.items():
            enabled = True
            if isinstance(config, dict):
                enabled = bool(config.get("enabled", True))
            if not enabled:
                continue

            step = trace_writer.create_step(
                run_id=run_id,
                step_type="io",
                step_id=f"delivery:{channel_name}",
                input_summary=f"trigger={trigger}, channel={channel_name}",
            )
            trace_writer.update_step_status(
                step.id,
                status="succeeded",
                output_summary=f"Delivery queued for channel={channel_name}",
                metrics={"channel": channel_name},
            )
            trace_writer.create_artifact(
                run_id=run_id,
                step_id=step.id,
                artifact_type="delivery",
                storage_key=f"bot/{bot_id}/runs/{run_id}/delivery/{channel_name}",
                meta={
                    "channel": channel_name,
                    "trigger": trigger,
                    "output_preview": output_text[:256],
                    "config": config if isinstance(config, dict) else {"value": str(config)},
                },
            )

    @rbac_guard(RESOURCE_BOT, "create", resource_id_resolver=_resolve_bot_create_id)
    async def create_bot(self, data: BotCreate) -> App:
        query = select(App).where(
            and_(
                App.tenant_id == self.ctx.tenant_id,
                App.workspace_id == self.ctx.workspace_id,
                App.type == "BOT",
                App.name == data.name,
            )
        )
        existing = self.db.exec(query).first()
        if existing:
            raise ValidationError(f"Bot with name '{data.name}' already exists")

        app = App(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            type="BOT",
            status="active",
            visibility=data.visibility,
            name=data.name,
            description=data.description,
            tags=data.tags,
            created_by=self.ctx.user_id,
        )
        self.db.add(app)
        self.db.commit()
        self.db.refresh(app)
        return app

    @rbac_guard(RESOURCE_BOT, "update", resource_id_arg="bot_id")
    async def update_bot(self, bot_id: str, data: BotUpdate) -> App:
        app = self._get_bot_app(bot_id)
        if data.name and data.name != app.name:
            query = select(App).where(
                and_(
                    App.tenant_id == self.ctx.tenant_id,
                    App.workspace_id == self.ctx.workspace_id,
                    App.type == "BOT",
                    App.name == data.name,
                    App.id != bot_id,
                )
            )
            existing = self.db.exec(query).first()
            if existing:
                raise ValidationError(f"Bot with name '{data.name}' already exists")
            app.name = data.name

        if data.description is not None:
            app.description = data.description
        if data.status is not None:
            app.status = data.status
        if data.visibility is not None:
            app.visibility = data.visibility
        if data.tags is not None:
            app.tags = data.tags
        app.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(app)
        return app

    @rbac_guard(RESOURCE_BOT, "read", resource_id_arg="bot_id")
    async def get_bot(self, bot_id: str) -> App:
        return self._get_bot_app(bot_id)

    @workspace_guard("read")
    async def list_bots(self, limit: int = 20, offset: int = 0) -> List[App]:
        query = select(App).where(
            and_(
                App.tenant_id == self.ctx.tenant_id,
                App.workspace_id == self.ctx.workspace_id,
                App.type == "BOT",
                App.status != "archived",
            )
        ).order_by(desc(App.created_at)).offset(offset).limit(limit)
        results = list(self.db.exec(query).all())
        if not results:
            return []
        if isinstance(results[0], App):
            return results
        return [row[0] for row in results if row]

    @rbac_guard(RESOURCE_BOT, "delete", resource_id_arg="bot_id")
    async def delete_bot(self, bot_id: str) -> None:
        app = self._get_bot_app(bot_id)
        app.status = "archived"
        app.updated_at = utc_now()
        self.db.commit()

    @rbac_guard(RESOURCE_BOT, "update", resource_id_arg="bot_id")
    async def create_version(self, bot_id: str, data: BotVersionCreate) -> AppVersion:
        app = self._get_bot_app(bot_id)
        spec = self._build_spec(data)
        validate_runtime_spec("bot.v1", spec, raise_on_error=True)

        version = AppVersion(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            app_id=bot_id,
            version=self._next_version_number(bot_id),
            status="draft",
            spec_schema="bot.v1",
            spec_json=spec,
            created_by=self.ctx.user_id,
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)

        app.current_version_id = version.id
        app.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(app)
        return version

    @rbac_guard(RESOURCE_BOT, "update", resource_id_arg="bot_id")
    async def update_version(self, bot_id: str, version_id: str, data: BotVersionUpdate) -> AppVersion:
        self._get_bot_app(bot_id)
        version = self._get_bot_version(bot_id, version_id)
        if version.status != "draft":
            raise ValidationError("Only draft versions can be updated")

        spec = self._merge_spec(version.spec_json or {}, data)
        validate_runtime_spec("bot.v1", spec, raise_on_error=True)
        version.spec_json = spec
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    @rbac_guard(RESOURCE_BOT, "read", resource_id_arg="bot_id")
    async def get_version(self, bot_id: str, version_id: str) -> AppVersion:
        self._get_bot_app(bot_id)
        return self._get_bot_version(bot_id, version_id)

    @rbac_guard(RESOURCE_BOT, "read", resource_id_arg="bot_id")
    async def list_versions(self, bot_id: str, limit: int = 20, offset: int = 0) -> List[AppVersion]:
        self._get_bot_app(bot_id)
        query = select(AppVersion).where(
            and_(
                AppVersion.app_id == bot_id,
                AppVersion.tenant_id == self.ctx.tenant_id,
                AppVersion.workspace_id == self.ctx.workspace_id,
            )
        ).order_by(desc(AppVersion.created_at)).offset(offset).limit(limit)
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, AppVersion) else item[0] for item in results]

    @rbac_guard(RESOURCE_BOT, "update", resource_id_arg="bot_id")
    async def publish_version(self, bot_id: str, version_id: str) -> App:
        app = self._get_bot_app(bot_id)
        self._get_bot_version(bot_id, version_id)
        self.publish_service.publish(bot_id, version_id)
        app.published_version_id = version_id
        app.updated_at = utc_now()
        self.db.add(app)
        self.db.commit()
        self.db.refresh(app)
        return app

    @rbac_guard(RESOURCE_BOT, "run", resource_id_arg="bot_id")
    async def execute_bot(
        self,
        bot_id: str,
        data: BotExecuteRequest,
    ) -> Dict[str, Any]:
        app = self._get_bot_app(bot_id)
        if data.version_id:
            use_current = False
            version_id = data.version_id
        else:
            use_current = True
            version_id = None

        effective_version_id = version_id or app.current_version_id
        if not effective_version_id:
            raise ValidationError("Bot has no current version")
        version = self._get_bot_version(bot_id, effective_version_id)
        if version.status == "published":
            self.publish_service.preflight.check(version.spec_json or {}, "bot.v1")

        messages = self._resolve_execute_messages(data)
        payload = {
            "messages": messages,
            "metadata": {
                "trigger": data.trigger,
                "event_payload": data.event_payload or {},
            },
        }
        result = await self.runtime_router.execute(
            app_id=bot_id,
            inputs=payload,
            version_id=effective_version_id if not use_current else None,
            use_current=use_current,
        )
        output = result.get("output") or {}
        output_text = output.get("text") or output.get("output") or ""
        self._record_channel_deliveries(
            bot_id=bot_id,
            run_id=result.get("run_id"),
            version=version,
            output_text=output_text,
            trigger=data.trigger,
        )
        return {
            "run_id": result.get("run_id"),
            "output": output_text,
            "model": output.get("model") or "",
            "tokens_prompt": output.get("tokens_prompt") or 0,
            "tokens_completion": output.get("tokens_completion") or 0,
            "finish_reason": output.get("finish_reason"),
        }

    @rbac_guard(RESOURCE_BOT, "read", resource_id_arg="bot_id")
    async def list_runs(
        self,
        bot_id: str,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> List[dict]:
        self._get_bot_app(bot_id)
        clauses = [
            Run.tenant_id == self.ctx.tenant_id,
            Run.workspace_id == self.ctx.workspace_id,
            Run.app_id == bot_id,
            Run.mode == "bot",
        ]
        if status:
            clauses.append(Run.status == status)
        if started_after:
            clauses.append(Run.created_at >= started_after)
        if started_before:
            clauses.append(Run.created_at <= started_before)
        query = select(Run).where(and_(*clauses)).order_by(desc(Run.created_at)).offset(offset).limit(limit)
        runs = self._unwrap_entities(list(self.db.exec(query).all()))
        return [
            {
                "id": run.id,
                "bot_id": bot_id,
                "status": run.status,
                "mode": run.mode,
                "user_id": run.user_id,
                "message_count": self._extract_message_count(run.input_summary),
                "input_summary": run.input_summary,
                "output_summary": run.output_summary,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            }
            for run in runs
        ]

    @rbac_guard(RESOURCE_BOT, "read", resource_id_arg="bot_id")
    async def get_run(self, bot_id: str, run_id: str) -> dict:
        query = select(Run).where(
            and_(
                Run.id == run_id,
                Run.tenant_id == self.ctx.tenant_id,
                Run.workspace_id == self.ctx.workspace_id,
                Run.app_id == bot_id,
                Run.mode == "bot",
            )
        )
        run = self.db.exec(query).first()
        run = self._unwrap_first_entity(run)
        if not run:
            raise NotFoundError(f"Run not found: {run_id}")

        steps_query = select(RunStep).where(
            and_(
                RunStep.run_id == run_id,
                RunStep.tenant_id == self.ctx.tenant_id,
                RunStep.workspace_id == self.ctx.workspace_id,
            )
        )
        steps = self._unwrap_entities(list(self.db.exec(steps_query).all()))

        artifacts_query = select(RunArtifact).where(
            and_(
                RunArtifact.run_id == run_id,
                RunArtifact.tenant_id == self.ctx.tenant_id,
                RunArtifact.workspace_id == self.ctx.workspace_id,
            )
        )
        artifacts = self._unwrap_entities(list(self.db.exec(artifacts_query).all()))

        costs_query = (
            select(RunCostEntry)
            .where(
                and_(
                    RunCostEntry.run_id == run_id,
                    RunCostEntry.tenant_id == self.ctx.tenant_id,
                    RunCostEntry.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(RunCostEntry.created_at)
        )
        costs = self._unwrap_entities(list(self.db.exec(costs_query).all()))

        cost_summary = {
            "tokens_prompt": 0,
            "tokens_completion": 0,
            "embedding_count": 0,
            "rerank_count": 0,
            "ms_total": 0,
            "storage_bytes": 0,
        }
        for entry in costs:
            if entry.prompt_tokens:
                cost_summary["tokens_prompt"] += int(entry.prompt_tokens)
            if entry.completion_tokens:
                cost_summary["tokens_completion"] += int(entry.completion_tokens)
            if entry.unit in ("embeddings", "embedding"):
                cost_summary["embedding_count"] += int(entry.quantity)
            if entry.unit == "rerank":
                cost_summary["rerank_count"] += int(entry.quantity)
            if entry.unit == "ms":
                cost_summary["ms_total"] += int(entry.quantity)
            if entry.unit == "bytes":
                cost_summary["storage_bytes"] += int(entry.quantity)

        return {
            "id": run.id,
            "bot_id": bot_id,
            "status": run.status,
            "mode": run.mode,
            "input_summary": run.input_summary,
            "output_summary": run.output_summary,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            "steps": [
                {
                    "id": step.id,
                    "step_id": step.step_id,
                    "status": step.status,
                    "input_summary": step.input_summary,
                    "output_summary": step.output_summary,
                    "started_at": step.started_at.isoformat() if step.started_at else None,
                    "ended_at": step.ended_at.isoformat() if step.ended_at else None,
                    "error_code": step.error_code,
                    "error_message": step.error_message,
                }
                for step in steps
            ],
            "artifacts": [
                {
                    "id": artifact.id,
                    "storage_key": artifact.storage_key,
                    "type": artifact.type,
                    "meta": artifact.meta_json,
                    "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
                }
                for artifact in artifacts
            ],
            "cost_summary": cost_summary,
            "costs": [
                {
                    "id": cost.id,
                    "run_id": cost.run_id,
                    "step_id": cost.step_id,
                    "currency": cost.currency,
                    "amount": float(cost.amount),
                    "unit": cost.unit,
                    "quantity": float(cost.quantity),
                    "provider": cost.provider,
                    "model_ref": cost.model_ref,
                    "tool_ref": cost.tool_ref,
                    "prompt_tokens": cost.prompt_tokens,
                    "completion_tokens": cost.completion_tokens,
                    "total_tokens": cost.total_tokens,
                    "created_at": cost.created_at.isoformat() if cost.created_at else None,
                }
                for cost in costs
            ],
        }

    @rbac_guard(RESOURCE_BOT, "read", resource_id_arg="bot_id")
    async def list_logs(
        self,
        bot_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        level: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        self._get_bot_app(bot_id)
        clauses = [
            RunStep.tenant_id == self.ctx.tenant_id,
            RunStep.workspace_id == self.ctx.workspace_id,
            RunStep.run_id == Run.id,
            Run.app_id == bot_id,
            Run.mode == "bot",
        ]
        if status:
            clauses.append(Run.status == status)
        if started_after:
            clauses.append(RunStep.created_at >= started_after)
        if started_before:
            clauses.append(RunStep.created_at <= started_before)
        query = (
            select(RunStep, Run)
            .where(and_(*clauses))
            .order_by(desc(RunStep.created_at))
            .limit(max(limit + offset, 200))
        )
        rows = list(self.db.exec(query).all())

        entries: List[Dict[str, Any]] = []
        for row in rows:
            step, run = row
            if step.error_code or step.status in {"failed", "cancelled"}:
                entry_level = "error"
            elif step.status in {"timeout", "retrying"}:
                entry_level = "warning"
            else:
                entry_level = "info"

            if level and entry_level != level:
                continue

            details = {
                "step_type": step.step_type,
                "node_id": step.node_id,
                "input_summary": step.input_summary,
                "output_summary": step.output_summary,
                "error_message": step.error_message,
                "run_status": run.status,
            }
            entries.append(
                {
                    "id": f"{run.id}:{step.id}",
                    "run_id": run.id,
                    "step_id": step.id,
                    "level": entry_level,
                    "message": step.error_message or step.output_summary or step.input_summary or step.step_id,
                    "code": step.error_code,
                    "status": step.status,
                    "created_at": step.created_at.isoformat() if step.created_at else None,
                    "details": details,
                }
            )

        return entries[offset : offset + limit]

    @rbac_guard(RESOURCE_BOT, "read", resource_id_arg="bot_id")
    async def get_metrics(self, bot_id: str, *, range_key: str = "7d") -> Dict[str, Any]:
        self._get_bot_app(bot_id)
        now = utc_now()
        started_after = now - self._resolve_metrics_window(range_key)

        runs_query = select(Run).where(
            and_(
                Run.tenant_id == self.ctx.tenant_id,
                Run.workspace_id == self.ctx.workspace_id,
                Run.app_id == bot_id,
                Run.mode == "bot",
                Run.created_at >= started_after,
            )
        )
        runs = self._unwrap_entities(list(self.db.exec(runs_query).all()))
        run_ids = [run.id for run in runs]

        runs_total = len(runs)
        runs_succeeded = sum(1 for run in runs if run.status == "succeeded")
        runs_failed = sum(1 for run in runs if run.status in {"failed", "cancelled"})
        success_rate = float(runs_succeeded / runs_total) if runs_total else 0.0

        latency_values: List[int] = []
        for run in runs:
            if run.duration_ms is not None:
                latency_values.append(int(run.duration_ms))
                continue
            if run.started_at and run.ended_at:
                delta = run.ended_at - run.started_at
                latency_values.append(int(delta.total_seconds() * 1000))
        avg_latency_ms = int(sum(latency_values) / len(latency_values)) if latency_values else None

        tokens_prompt = 0
        tokens_completion = 0
        ms_total = 0
        storage_bytes = 0
        if run_ids:
            costs_query = select(RunCostEntry).where(
                and_(
                    RunCostEntry.tenant_id == self.ctx.tenant_id,
                    RunCostEntry.workspace_id == self.ctx.workspace_id,
                    RunCostEntry.run_id.in_(run_ids),
                )
            )
            costs = self._unwrap_entities(list(self.db.exec(costs_query).all()))
            tokens_prompt = sum(int(item.prompt_tokens or 0) for item in costs)
            tokens_completion = sum(int(item.completion_tokens or 0) for item in costs)
            ms_total = sum(int(item.quantity or 0) for item in costs if item.unit == "ms")
            storage_bytes = sum(int(item.quantity or 0) for item in costs if item.unit == "bytes")

        bucket_format = "%Y-%m-%dT%H:00:00Z" if range_key == "24h" else "%Y-%m-%d"
        bucket_map: Dict[str, Dict[str, Any]] = {}
        for run in runs:
            bucket = (run.created_at or run.started_at or now).strftime(bucket_format)
            item = bucket_map.setdefault(
                bucket,
                {
                    "bucket": bucket,
                    "runs_total": 0,
                    "runs_succeeded": 0,
                    "runs_failed": 0,
                    "tokens_prompt": 0,
                    "tokens_completion": 0,
                    "latencies": [],
                },
            )
            item["runs_total"] += 1
            if run.status == "succeeded":
                item["runs_succeeded"] += 1
            elif run.status in {"failed", "cancelled"}:
                item["runs_failed"] += 1
            if run.duration_ms is not None:
                item["latencies"].append(int(run.duration_ms))
            elif run.started_at and run.ended_at:
                item["latencies"].append(int((run.ended_at - run.started_at).total_seconds() * 1000))

        if run_ids:
            costs_query = select(RunCostEntry, Run).where(
                and_(
                    RunCostEntry.tenant_id == self.ctx.tenant_id,
                    RunCostEntry.workspace_id == self.ctx.workspace_id,
                    RunCostEntry.run_id == Run.id,
                    Run.id.in_(run_ids),
                )
            )
            for cost, run in list(self.db.exec(costs_query).all()):
                bucket = (run.created_at or run.started_at or now).strftime(bucket_format)
                item = bucket_map.setdefault(
                    bucket,
                    {
                        "bucket": bucket,
                        "runs_total": 0,
                        "runs_succeeded": 0,
                        "runs_failed": 0,
                        "tokens_prompt": 0,
                        "tokens_completion": 0,
                        "latencies": [],
                    },
                )
                item["tokens_prompt"] += int(cost.prompt_tokens or 0)
                item["tokens_completion"] += int(cost.completion_tokens or 0)

        points: List[Dict[str, Any]] = []
        for bucket in sorted(bucket_map.keys()):
            item = bucket_map[bucket]
            latencies = item.pop("latencies")
            item["avg_latency_ms"] = int(sum(latencies) / len(latencies)) if latencies else None
            points.append(item)

        active_users = len({run.user_id for run in runs if run.user_id})
        success_percent = int((runs_succeeded / runs_total) * 100) if runs_total else 0
        failed_percent = int((runs_failed / runs_total) * 100) if runs_total else 0
        running_percent = max(0, 100 - success_percent - failed_percent) if runs_total else 0
        usage_distribution = [
            {"name": "succeeded", "value": success_percent},
            {"name": "failed", "value": failed_percent},
            {"name": "other", "value": running_percent},
        ]
        avg_tokens_per_run = int((tokens_prompt + tokens_completion) / runs_total) if runs_total else 0
        resource_usage = {
            "cpu_percent": min(100, int((avg_latency_ms or 0) / 50)),
            "memory_percent": min(100, int(avg_tokens_per_run / 50)),
            "network_percent": min(100, int(runs_total * 5)),
            "storage_percent": min(100, int(storage_bytes / (1024 * 1024) * 10)),
            "ms_total": ms_total,
            "storage_bytes": storage_bytes,
        }

        return {
            "runs_total": runs_total,
            "runs_succeeded": runs_succeeded,
            "runs_failed": runs_failed,
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency_ms,
            "tokens_prompt": tokens_prompt,
            "tokens_completion": tokens_completion,
            "active_users": active_users,
            "usage_distribution": usage_distribution,
            "resource_usage": resource_usage,
            "points": points,
        }
