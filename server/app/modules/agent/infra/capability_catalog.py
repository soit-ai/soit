"""SQL-backed anti-corruption adapter for Agent capability reads."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.modules.knowledge.domain.models import Knowledge, KnowledgeIndex
from app.modules.modelhub.domain.models import ProviderModel
from app.modules.plugin.domain.models import PluginInstalledArtifact
from app.modules.workflow.domain.models import Workflow, WorkflowVersion


def _item(
    *,
    ref: str,
    kind: str,
    name: str,
    source_kind: str,
    source_id: str | None = None,
    source_version: str | None = None,
    metadata_json: dict[str, Any] | None = None,
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


class SqlAgentCapabilityCatalog:
    """Project foreign domain rows into stable Agent capability records."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    @staticmethod
    def _scalar(row: Any) -> Any:
        if row is None:
            return None
        try:
            return row[0]
        except (KeyError, TypeError):
            return row

    def list_model_capabilities(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(ProviderModel).where(
                and_(
                    ProviderModel.tenant_id == self.ctx.tenant_id,
                    ProviderModel.workspace_id == self.ctx.workspace_id,
                    ProviderModel.status == "active",
                )
            )
        ).scalars()
        return [
            _item(
                ref=f"model:{model.provider_kind}:{model.model_id}",
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
                    "status": model.status,
                    "capabilities_json": model.capabilities_json or {},
                    "config_json": model.config_json or {},
                    "raw_meta": model.raw_meta or {},
                },
            )
            for model in rows
        ]

    def list_knowledge_capabilities(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(Knowledge).where(
                and_(
                    Knowledge.tenant_id == self.ctx.tenant_id,
                    Knowledge.workspace_id == self.ctx.workspace_id,
                    Knowledge.deleted_at.is_(None),
                    Knowledge.status != "archived",
                )
            )
        ).scalars()
        return [
            _item(
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
            for knowledge in rows
        ]

    def list_workflow_capabilities(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(Workflow).where(
                and_(
                    Workflow.tenant_id == self.ctx.tenant_id,
                    Workflow.workspace_id == self.ctx.workspace_id,
                    Workflow.deleted_at.is_(None),
                    Workflow.status != "archived",
                )
            )
        ).scalars()
        return [
            _item(
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
            for workflow in rows
        ]

    def list_plugin_capabilities(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(PluginInstalledArtifact).where(
                and_(
                    PluginInstalledArtifact.tenant_id == self.ctx.tenant_id,
                    PluginInstalledArtifact.workspace_id == self.ctx.workspace_id,
                    PluginInstalledArtifact.enabled.is_(True),
                    PluginInstalledArtifact.state == "enabled",
                )
            )
        ).scalars()
        items: list[dict[str, Any]] = []
        for artifact in rows:
            metadata = artifact.metadata_json or {}
            base_metadata = {
                **metadata,
                "plugin_id": artifact.plugin_id,
                "plugin_version_id": artifact.plugin_version_id,
                "installation_id": artifact.installation_id,
                "artifact_kind": artifact.artifact_kind,
                "artifact_ref": artifact.artifact_ref,
            }
            if artifact.artifact_kind == "skill":
                skill = metadata.get("skill") or {}
                items.append(
                    _item(
                        ref=artifact.artifact_ref,
                        kind="skill",
                        name=str(skill.get("name") or artifact.artifact_ref.split(":", 1)[-1]),
                        source_kind="plugin",
                        source_id=artifact.plugin_id,
                        source_version=artifact.plugin_version_id,
                        metadata_json=base_metadata,
                    )
                )
            elif artifact.artifact_kind == "mcp_server":
                mcp = metadata.get("mcp_server") or {}
                server_name = str(mcp.get("name") or artifact.artifact_ref.split(":", 1)[-1])
                items.append(
                    _item(
                        ref=artifact.artifact_ref,
                        kind="mcp_server",
                        name=server_name,
                        source_kind="plugin",
                        source_id=artifact.plugin_id,
                        source_version=artifact.plugin_version_id,
                        metadata_json=base_metadata,
                    )
                )
                for capability in (mcp.get("capabilities_json") or {}).get("tools") or []:
                    if not isinstance(capability, dict):
                        continue
                    key = str(capability.get("name") or capability.get("id") or "").strip()
                    if key:
                        items.append(
                            _item(
                                ref=f"mcp_tool:{server_name}:{key}",
                                kind="tool",
                                name=str(capability.get("name") or key),
                                source_kind="plugin",
                                source_id=artifact.plugin_id,
                                source_version=artifact.plugin_version_id,
                                metadata_json={**base_metadata, "capability": capability},
                            )
                        )
        return items

    def resolve_skill_context(self, skill_refs: list[str]) -> str | None:
        artifacts = self.db.execute(
            select(PluginInstalledArtifact).where(
                and_(
                    PluginInstalledArtifact.tenant_id == self.ctx.tenant_id,
                    PluginInstalledArtifact.workspace_id == self.ctx.workspace_id,
                    PluginInstalledArtifact.artifact_kind == "skill",
                    PluginInstalledArtifact.enabled.is_(True),
                    PluginInstalledArtifact.state == "enabled",
                )
            )
        ).scalars().all()
        blocks: list[str] = []
        for skill_ref in skill_refs:
            skill_key = skill_ref.split(":", 1)[1] if skill_ref.startswith("skill:") else skill_ref
            artifact = next(
                (
                    candidate
                    for candidate in artifacts
                    if candidate.artifact_ref in {skill_ref, f"skill:{skill_key}"}
                    or str((candidate.metadata_json or {}).get("skill", {}).get("name") or "") == skill_key
                ),
                None,
            )
            if not artifact:
                continue
            skill = (artifact.metadata_json or {}).get("skill") or {}
            spec = skill.get("spec_json") or skill.get("spec") or {}
            instruction = (
                spec.get("instructions")
                or spec.get("system_prompt")
                or spec.get("prompt")
                or spec.get("description")
                or json.dumps(spec, ensure_ascii=True, sort_keys=True)
            )
            blocks.append(f"[{skill_ref}]\n{instruction}")
        return "Bound skill context:\n" + "\n\n".join(blocks) if blocks else None

    def workflow_input_schema(self, workflow_ref: str) -> dict[str, Any]:
        fallback: dict[str, Any] = {"type": "object", "additionalProperties": True}
        workflow_id = workflow_ref.split(":")[-1]
        workflow = self.db.execute(
            select(Workflow).where(
                and_(
                    Workflow.tenant_id == self.ctx.tenant_id,
                    Workflow.workspace_id == self.ctx.workspace_id,
                    Workflow.id == workflow_id,
                    Workflow.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if not workflow:
            return fallback
        version_id = workflow.published_version_id or workflow.current_version_id
        if not version_id:
            return fallback
        version = self.db.execute(
            select(WorkflowVersion).where(
                and_(
                    WorkflowVersion.tenant_id == self.ctx.tenant_id,
                    WorkflowVersion.workspace_id == self.ctx.workspace_id,
                    WorkflowVersion.id == version_id,
                    WorkflowVersion.workflow_id == workflow.id,
                )
            )
        ).scalar_one_or_none()
        return ((version.spec_json or {}).get("inputs_schema") or fallback) if version else fallback

    def knowledge_runtime_defaults(self, knowledge_ref: str) -> dict[str, str]:
        knowledge_id = knowledge_ref.split(":")[-1]
        knowledge = self.db.execute(
            select(Knowledge).where(
                and_(
                    Knowledge.tenant_id == self.ctx.tenant_id,
                    Knowledge.workspace_id == self.ctx.workspace_id,
                    Knowledge.id == knowledge_id,
                    Knowledge.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if not knowledge:
            return {}
        filters = [
            KnowledgeIndex.tenant_id == self.ctx.tenant_id,
            KnowledgeIndex.workspace_id == self.ctx.workspace_id,
            KnowledgeIndex.knowledge_id == knowledge.id,
            KnowledgeIndex.deleted_at.is_(None),
            (
                KnowledgeIndex.id == knowledge.default_index_id
                if knowledge.default_index_id
                else KnowledgeIndex.is_primary.is_(True)
            ),
        ]
        index = self.db.execute(select(KnowledgeIndex).where(and_(*filters))).scalar_one_or_none()
        defaults: dict[str, str] = {}
        if knowledge.default_embedding_model_ref:
            defaults["embedding_model"] = knowledge.default_embedding_model_ref
        if index and index.collection_name:
            defaults["knowledge_collection"] = index.collection_name
        return defaults
