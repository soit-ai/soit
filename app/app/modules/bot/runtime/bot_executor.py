"""bot_executor

Bot runtime executor for bot.v1 specs.
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ValidationError
from app.kernel.events.bus import EventBus
from app.modules.chat.runtime.chat_executor import ChatExecutorV1


class BotExecutorV1:
    """Bot executor that runs embedded chat config."""

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
        self.chat_executor = ChatExecutorV1(db, ctx, event_bus=event_bus)

    async def execute(
        self,
        *,
        app: Any,
        version: Any,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        spec = version.spec_json or {}
        chat_spec = spec.get("chat")
        if not isinstance(chat_spec, dict):
            raise ValidationError("Bot spec missing chat configuration")
        return await self.chat_executor.execute(
            app=app,
            version=version,
            inputs=inputs,
            spec_override=chat_spec,
            mode="bot",
        )
