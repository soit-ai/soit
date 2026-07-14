"""Plugin skill runtime adapter."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.plugins.interface import PluginRuntimePort
from app.modules.plugin.domain.models import PluginInstalledArtifact


class DatabaseSkillRuntimePort(PluginRuntimePort):
    """Resolve installed plugin skills into agent runtime context."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_tools(self, *, plugin_name: str, version: str, ctx: RequestContext) -> list[dict[str, Any]]:
        return []

    async def invoke(
        self,
        *,
        plugin_name: str,
        version: str,
        tool_name: str,
        input_json: dict[str, Any],
        ctx: RequestContext,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        raise ValidationError("Skill runtime does not invoke plugin tools")

    def resolve_skill_context(
        self,
        *,
        skill_refs: list[str],
        ctx: RequestContext,
    ) -> str | None:
        blocks: list[str] = []
        for skill_ref in skill_refs:
            artifact = self._find_enabled_skill(skill_ref=skill_ref, ctx=ctx)
            if not artifact:
                continue
            blocks.append(f"[{skill_ref}]\n{self._render_instruction(artifact)}")
        if not blocks:
            return None
        return "Bound skill context:\n" + "\n\n".join(blocks)

    def _find_enabled_skill(self, *, skill_ref: str, ctx: RequestContext) -> PluginInstalledArtifact | None:
        skill_key = skill_ref.split(":", 1)[1] if skill_ref.startswith("skill:") else skill_ref
        query = select(PluginInstalledArtifact).where(
            and_(
                PluginInstalledArtifact.tenant_id == ctx.tenant_id,
                PluginInstalledArtifact.workspace_id == ctx.workspace_id,
                PluginInstalledArtifact.artifact_kind == "skill",
                PluginInstalledArtifact.enabled.is_(True),
                PluginInstalledArtifact.state == "enabled",
            )
        )
        for row in list(self.db.exec(query).all()):
            artifact = row[0] if hasattr(row, "__getitem__") and not isinstance(row, PluginInstalledArtifact) else row
            skill = (artifact.metadata_json or {}).get("skill") or {}
            name = str(skill.get("name") or artifact.artifact_ref.split(":", 1)[-1])
            if artifact.artifact_ref == skill_ref or artifact.artifact_ref == f"skill:{skill_key}" or name == skill_key:
                return artifact
        return None

    @staticmethod
    def _render_instruction(artifact: PluginInstalledArtifact) -> str:
        skill = (artifact.metadata_json or {}).get("skill") or {}
        spec = skill.get("spec_json") or skill.get("spec") or {}
        instruction = (
            spec.get("instructions")
            or spec.get("system_prompt")
            or spec.get("prompt")
            or spec.get("description")
        )
        if instruction:
            return str(instruction)
        return json.dumps(spec, ensure_ascii=True, sort_keys=True)
