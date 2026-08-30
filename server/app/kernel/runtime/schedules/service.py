"""Schedules: create, change, and work out when each one next fires.

Firing itself lives in the worker. This module owns the record and the rules
around it, so an invalid expression or an impossible target is refused when
somebody saves it rather than discovered at two in the morning.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, desc, select

from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.schedules import Schedule
from app.kernel.runtime.schedules.cron import (
    CronError,
    next_fire_after,
    parse,
    resolve_timezone,
)

TARGET_KINDS = ("agent", "workflow")


class ScheduleService:
    """Read and write schedules for one workspace."""

    def __init__(self, db, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def _scope(self) -> list:
        return [
            Schedule.tenant_id == self.ctx.tenant_id,
            Schedule.workspace_id == self.ctx.workspace_id,
        ]

    def list(self, *, enabled: bool | None = None, limit: int = 100, offset: int = 0) -> list[Schedule]:
        clauses = self._scope()
        if enabled is not None:
            clauses.append(Schedule.enabled == enabled)
        query = (
            select(Schedule)
            .where(and_(*clauses))
            .order_by(desc(Schedule.created_at))
            .offset(offset)
            .limit(limit)
        )
        rows = list(self.db.exec(query).all())
        return [row if hasattr(row, "id") else row[0] for row in rows]

    def get(self, schedule_id: str) -> Schedule:
        query = select(Schedule).where(and_(Schedule.id == schedule_id, *self._scope()))
        row = self.db.exec(query).first()
        schedule = row if row is None or hasattr(row, "id") else row[0]
        if schedule is None:
            raise NotFoundError(f"Schedule not found: {schedule_id}")
        return schedule

    @staticmethod
    def _validate(cron: str, timezone: str, target_kind: str) -> None:
        """Refuse what could not fire, at the moment somebody saves it."""
        if target_kind not in TARGET_KINDS:
            raise ValidationError(f"A schedule targets an agent or a workflow, not {target_kind!r}")
        try:
            parse(cron)
            resolve_timezone(timezone)
        except CronError as exc:
            raise ValidationError(str(exc)) from exc

    def create(
        self,
        *,
        name: str,
        target_kind: str,
        target_id: str,
        cron: str,
        timezone: str = "UTC",
        description: str | None = None,
        inputs: dict | None = None,
        enabled: bool = True,
        catch_up: bool = False,
    ) -> Schedule:
        self._validate(cron, timezone, target_kind)
        now = utc_now()
        schedule = Schedule(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            name=name.strip(),
            description=(description or "").strip() or None,
            target_kind=target_kind,
            target_id=target_id,
            input_json=inputs or {},
            cron=cron.strip(),
            timezone=timezone,
            enabled=enabled,
            catch_up=catch_up,
            # A disabled schedule has no next firing: showing one would promise
            # something that is not going to happen.
            next_fire_at=next_fire_after(cron, now, timezone=timezone) if enabled else None,
            created_by=self.ctx.user_id,
        )
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def update(
        self,
        schedule_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        cron: str | None = None,
        timezone: str | None = None,
        inputs: dict | None = None,
        enabled: bool | None = None,
        catch_up: bool | None = None,
    ) -> Schedule:
        schedule = self.get(schedule_id)
        if cron is not None or timezone is not None:
            self._validate(
                cron if cron is not None else schedule.cron,
                timezone if timezone is not None else schedule.timezone,
                schedule.target_kind,
            )
        if name is not None:
            schedule.name = name.strip()
        if description is not None:
            schedule.description = description.strip() or None
        if cron is not None:
            schedule.cron = cron.strip()
        if timezone is not None:
            schedule.timezone = timezone
        if inputs is not None:
            schedule.input_json = inputs
        if catch_up is not None:
            schedule.catch_up = catch_up
        if enabled is not None:
            schedule.enabled = enabled

        # Recomputed from now, not from the old next firing: changing the
        # expression must not leave a firing scheduled by the previous one.
        schedule.next_fire_at = (
            next_fire_after(schedule.cron, utc_now(), timezone=schedule.timezone)
            if schedule.enabled
            else None
        )
        schedule.updated_at = utc_now()
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def delete(self, schedule_id: str) -> None:
        schedule = self.get(schedule_id)
        self.db.delete(schedule)
        self.db.commit()

    def preview(self, cron: str, timezone: str = "UTC", *, count: int = 5) -> list[datetime]:
        """The next few firings, so somebody can check an expression before saving."""
        self._validate(cron, timezone, "agent")
        moments: list[datetime] = []
        cursor = utc_now()
        for _ in range(max(1, min(count, 20))):
            cursor = next_fire_after(cron, cursor, timezone=timezone)
            moments.append(cursor)
        return moments
