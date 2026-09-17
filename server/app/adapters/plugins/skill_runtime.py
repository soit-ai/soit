"""Plugin skill runtime adapter."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.plugins.interface import PluginRuntimePort
from app.modules.plugin.domain.models import PluginInstalledArtifact


class DatabaseSkillRuntimePort(PluginRuntimePort):
    """Resolve installed plugin skills into agent runtime context."""

    def __init__(self, db: AsyncSession) -> None:
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

    async def resolve_skill_context(
        self,
        *,
        skill_refs: list[str],
        ctx: RequestContext,
    ) -> str | None:
        if not skill_refs:
            return None
        artifacts = await self._enabled_skills(ctx)
        blocks: list[str] = []
        for skill_ref in skill_refs:
            artifact = self._match_skill(artifacts, skill_ref)
            if not artifact:
                continue
            blocks.append(f"[{skill_ref}]\n{self._render_instruction(artifact)}")
        if not blocks:
            return None
        return "Bound skill context:\n" + "\n\n".join(blocks)

    async def _enabled_skills(self, ctx: RequestContext) -> list[PluginInstalledArtifact]:
        query = select(PluginInstalledArtifact).where(
            and_(
                PluginInstalledArtifact.tenant_id == ctx.tenant_id,
                PluginInstalledArtifact.workspace_id == ctx.workspace_id,
                PluginInstalledArtifact.artifact_kind == "skill",
                PluginInstalledArtifact.enabled.is_(True),
                PluginInstalledArtifact.state == "enabled",
            )
        )
        return list((await self.db.exec(query)).scalars().all())

    @staticmethod
    def _match_skill(
        artifacts: list[PluginInstalledArtifact], skill_ref: str
    ) -> PluginInstalledArtifact | None:
        skill_key = skill_ref.split(":", 1)[1] if skill_ref.startswith("skill:") else skill_ref
        for artifact in artifacts:
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
