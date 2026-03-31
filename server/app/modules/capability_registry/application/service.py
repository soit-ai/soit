"""Capability registry application service."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.registry.deps import get_registry
from app.modules.integrations.mcp.domain.models import MCPServer
from app.modules.knowledge.domain.models import Knowledge
from app.modules.modelhub.domain.models import ProviderModel
from app.modules.skill.domain.models import Skill
from app.modules.workflow.domain.models import Workflow


class CapabilityRegistryService:
    """Aggregate runtime capabilities from the kernel registry and local tables."""

    _BUILTIN_TOOL_REFS = {
        "tool:http:request",
        "tool:function:time_now",
        "tool:function:random_int",
        "tool:function:knowledge_query",
    }

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx
        self.registry = get_registry()

    def _item(
        self,
        *,
        ref: str,
        kind: str,
        name: str,
        source_kind: str,
        source_id: Optional[str] = None,
        source_version: Optional[str] = None,
        metadata_json: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return {
            "ref": ref,
            "kind": kind,
            "name": name,
            "source_kind": source_kind,
            "source_id": source_id,
            "source_version": source_version,
            "metadata_json": metadata_json or {},
        }

    def _tool_source_kind(self, ref: str, payload: dict[str, Any]) -> str:
        explicit = (payload.get("source_kind") or "").strip().lower()
        if explicit in {"builtin", "native", "plugin", "mcp"}:
            return explicit
        if payload.get("plugin"):
            return "plugin"
        if payload.get("mcp"):
            return "mcp"
        if payload.get("builtin") or ref in self._BUILTIN_TOOL_REFS:
            return "builtin"
        return "native"

    def _tool_capability_from_registry(self, key, payload: dict[str, Any]) -> dict[str, Any]:
        ref = key.name
        tool_spec = payload.get("tool_spec") or {}
        plugin = payload.get("plugin") or {}
        source_kind = self._tool_source_kind(ref, payload)
        source_id = payload.get("source_id")
        source_version = payload.get("source_version") or key.version
        if source_kind == "plugin":
            source_id = source_id or plugin.get("name")
            source_version = source_version or plugin.get("version")
        elif source_kind == "mcp":
            mcp_meta = payload.get("mcp") or {}
            source_id = source_id or mcp_meta.get("server_id") or mcp_meta.get("server_name") or mcp_meta.get("name")
            source_version = source_version or mcp_meta.get("server_version")
        elif source_kind == "builtin":
            source_id = source_id or ref
        else:
            source_id = source_id or ref
        metadata = {
            "registry_kind": key.kind,
            "registry_version": key.version,
            "tool_spec": tool_spec,
        }
        metadata.update({k: v for k, v in payload.items() if k not in {"tool_spec"}})
        return self._item(
            ref=ref,
            kind="tool",
            name=str(tool_spec.get("name") or ref.split(":")[-1]),
            source_kind=source_kind,
            source_id=source_id,
            source_version=source_version,
            metadata_json=metadata,
        )

    def _model_capabilities(self) -> list[dict[str, Any]]:
        query = select(ProviderModel).where(
            and_(
                ProviderModel.tenant_id == self.ctx.tenant_id,
                ProviderModel.workspace_id == self.ctx.workspace_id,
                ProviderModel.enabled.is_(True),
            )
        )
        rows = list(self.db.exec(query).all())
        items: list[dict[str, Any]] = []
        for row in rows:
            model = row[0] if hasattr(row, "__getitem__") and not isinstance(row, ProviderModel) else row
            ref = f"model:{model.provider_kind}:{model.model_id}"
            items.append(
                self._item(
                    ref=ref,
                    kind="model",
                    name=str(model.display_name or model.model_id),
                    source_kind="native",
                    source_id=model.id,
                    source_version=model.platform_model_id,
                    metadata_json={
                        "provider_id": model.provider_id,
                        "provider_kind": model.provider_kind,
                        "model_id": model.model_id,
                        "display_name": model.display_name,
                        "source": model.source,
                        "sync_status": model.sync_status,
                        "enabled": model.enabled,
                        "capabilities_json": model.capabilities_json or {},
                        "config_json": model.config_json or {},
                        "raw_meta": model.raw_meta or {},
                    },
                )
            )
        return items

    def _knowledge_capabilities(self) -> list[dict[str, Any]]:
        query = select(Knowledge).where(
            and_(
                Knowledge.tenant_id == self.ctx.tenant_id,
                Knowledge.workspace_id == self.ctx.workspace_id,
                Knowledge.deleted_at.is_(None),
                Knowledge.status != "archived",
            )
        )
        rows = list(self.db.exec(query).all())
        items: list[dict[str, Any]] = []
        for row in rows:
            knowledge = row[0] if hasattr(row, "__getitem__") and not isinstance(row, Knowledge) else row
            items.append(
                self._item(
                    ref=f"knowledge:{knowledge.id}",
                    kind="knowledge",
                    name=knowledge.name,
                    source_kind="native",
                    source_id=knowledge.id,
                    metadata_json={
                        "type": knowledge.type,
                        "status": knowledge.status,
                        "visibility": knowledge.visibility,
                        "default_index_id": knowledge.default_index_id,
                        "doc_count": knowledge.doc_count,
                        "chunk_count": knowledge.chunk_count,
                        "tags": knowledge.tags or [],
                    },
                )
            )
        return items

    def _workflow_capabilities(self) -> list[dict[str, Any]]:
        query = select(Workflow).where(
            and_(
                Workflow.tenant_id == self.ctx.tenant_id,
                Workflow.workspace_id == self.ctx.workspace_id,
                Workflow.deleted_at.is_(None),
                Workflow.status != "archived",
            )
        )
        rows = list(self.db.exec(query).all())
        items: list[dict[str, Any]] = []
        for row in rows:
            workflow = row[0] if hasattr(row, "__getitem__") and not isinstance(row, Workflow) else row
            items.append(
                self._item(
                    ref=f"wf:{workflow.id}",
                    kind="workflow",
                    name=workflow.name,
                    source_kind="native",
                    source_id=workflow.id,
                    source_version=workflow.published_version_id or workflow.current_version_id,
                    metadata_json={
                        "status": workflow.status,
                        "visibility": workflow.visibility,
                        "category": workflow.category,
                        "summary": workflow.summary,
                        "current_version_id": workflow.current_version_id,
                        "published_version_id": workflow.published_version_id,
                    },
                )
            )
        return items

    def _skill_capabilities(self) -> list[dict[str, Any]]:
        query = select(Skill).where(
            and_(
                Skill.tenant_id == self.ctx.tenant_id,
                Skill.workspace_id == self.ctx.workspace_id,
                Skill.deleted_at.is_(None),
                Skill.status != "archived",
            )
        )
        rows = list(self.db.exec(query).all())
        items: list[dict[str, Any]] = []
        for row in rows:
            skill = row[0] if hasattr(row, "__getitem__") and not isinstance(row, Skill) else row
            items.append(
                self._item(
                    ref=f"skill:{skill.id}",
                    kind="skill",
                    name=skill.name,
                    source_kind="native",
                    source_id=skill.id,
                    source_version=skill.published_version_id or skill.current_version_id,
                    metadata_json={
                        "status": skill.status,
                        "visibility": skill.visibility,
                        "category": skill.category,
                        "current_version_id": skill.current_version_id,
                        "published_version_id": skill.published_version_id,
                    },
                )
            )
        return items

    def _tool_capabilities(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for key, payload in self.registry.list(
            kind="tool",
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
        ):
            payload_dict = payload if isinstance(payload, dict) else {}
            items.append(self._tool_capability_from_registry(key, payload_dict))
        return items

    def _mcp_tool_capabilities(self) -> list[dict[str, Any]]:
        query = select(MCPServer).where(
            and_(
                MCPServer.tenant_id == self.ctx.tenant_id,
                MCPServer.workspace_id == self.ctx.workspace_id,
                MCPServer.deleted_at.is_(None),
                MCPServer.enabled.is_(True),
                MCPServer.status != "archived",
            )
        )
        rows = list(self.db.exec(query).all())
        items: list[dict[str, Any]] = []
        for row in rows:
            server = row[0] if hasattr(row, "__getitem__") and not isinstance(row, MCPServer) else row
            capabilities = server.capabilities_json or {}
            for item in list(capabilities.get("tools") or []):
                if not isinstance(item, dict):
                    continue
                capability_key = str(item.get("name") or item.get("id") or "").strip()
                if not capability_key:
                    continue
                items.append(
                    self._item(
                        ref=f"mcp_tool:{server.name}:{capability_key}",
                        kind="tool",
                        name=str(item.get("name") or capability_key),
                        source_kind="mcp",
                        source_id=server.id,
                        metadata_json={
                            "server_id": server.id,
                            "server_name": server.name,
                            "capability_key": capability_key,
                            "capability_name": item.get("name") or capability_key,
                            "description": item.get("description"),
                            "transport": server.transport,
                            "endpoint": server.endpoint,
                            "capability_json": item,
                        },
                    )
                )
        return items

    async def list_capabilities(
        self,
        *,
        kind: Optional[str] = None,
        source_kind: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Return the current runtime capability snapshot."""
        items = [
            *self._model_capabilities(),
            *self._knowledge_capabilities(),
            *self._workflow_capabilities(),
            *self._skill_capabilities(),
            *self._tool_capabilities(),
            *self._mcp_tool_capabilities(),
        ]
        deduped: dict[str, dict[str, Any]] = {}
        for item in items:
            deduped.setdefault(item["ref"], item)
        filtered = [
            item
            for item in deduped.values()
            if (kind is None or item["kind"] == kind)
            and (source_kind is None or item["source_kind"] == source_kind)
        ]
        ordered = sorted(filtered, key=lambda entry: (entry["kind"], entry["source_kind"], entry["ref"]))
        return ordered
