"""Five-field cron expressions, and when they next fire.

Written here rather than pulled in because the surface actually used is small
and fully specified: minute, hour, day-of-month, month, day-of-week, with `*`,
lists, ranges and steps. The behaviour that catches people out -- how
day-of-month and day-of-week combine, and what a local time that does not exist
means across a daylight-saving change -- is decided explicitly below rather
than inherited from whatever a library happens to do.

Nothing here reads or writes state.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FIELD_RANGES = {
    "minute": (0, 59),
    "hour": (0, 23),
    "day": (1, 31),
    "month": (1, 12),
    "weekday": (0, 6),
}
FIELD_ORDER = ("minute", "hour", "day", "month", "weekday")

MAX_LOOKAHEAD_DAYS = 366 * 4
"""Far enough to find the next 29 February; beyond that an expression is wrong."""


class CronError(ValueError):
    """The expression cannot be parsed, or can never fire."""


def _parse_field(raw: str, field: str) -> set[int]:
    low, high = FIELD_RANGES[field]
    values: set[int] = set()

    for part in raw.split(","):
        part = part.strip()
        if not part:
            raise CronError(f"Empty value in the {field} field")

        step = 1
        if "/" in part:
            part, _, step_text = part.partition("/")
            if not step_text.isdigit() or int(step_text) < 1:
                raise CronError(f"Invalid step in the {field} field")
            step = int(step_text)
            part = part or "*"

        if part == "*":
            start, end = low, high
        elif "-" in part:
            start_text, _, end_text = part.partition("-")
            start, end = _as_int(start_text, field), _as_int(end_text, field)
            if start > end:
                raise CronError(f"Reversed range in the {field} field")
        else:
            start = end = _as_int(part, field)

        values.update(range(start, end + 1, step))

    if not values:
        raise CronError(f"The {field} field matches nothing")
    return values


def _as_int(text: str, field: str) -> int:
    low, high = FIELD_RANGES[field]
    text = text.strip()
    # Sunday is 0, and 7 is the other spelling of it that people expect to work.
    if field == "weekday" and text == "7":
        return 0
    if not text.isdigit():
        raise CronError(f"Non-numeric value in the {field} field: {text!r}")
    value = int(text)
    if not low <= value <= high:
        raise CronError(f"{value} is out of range for the {field} field")
    return value


class CronExpression:
    """A parsed five-field cron expression."""

    def __init__(self, expression: str) -> None:
        fields = (expression or "").split()
        if len(fields) != 5:
            raise CronError("A cron expression has five fields")
        self.expression = " ".join(fields)
        self.matched = {
            name: _parse_field(value, name)
            for name, value in zip(FIELD_ORDER, fields, strict=True)
        }
        self.day_restricted = fields[2].strip() != "*"
        self.weekday_restricted = fields[4].strip() != "*"

    def matches(self, moment: datetime) -> bool:
        """Whether a local wall-clock minute is one this expression fires on.

        Day-of-month and day-of-week are ORed when both are restricted, which
        is what cron has always done and what "0 2 1 * 1" means: the first of
        the month, and every Monday.
        """
        if moment.minute not in self.matched["minute"]:
            return False
        if moment.hour not in self.matched["hour"]:
            return False
        if moment.month not in self.matched["month"]:
            return False

        day_ok = moment.day in self.matched["day"]
        # Python weekday: Monday is 0. Cron: Sunday is 0.
        weekday_ok = ((moment.weekday() + 1) % 7) in self.matched["weekday"]
        if self.day_restricted and self.weekday_restricted:
            return day_ok or weekday_ok
        if self.day_restricted:
            return day_ok
        if self.weekday_restricted:
            return weekday_ok
        return True


def parse(expression: str) -> CronExpression:
    """Parse an expression, raising CronError if it cannot fire."""
    return CronExpression(expression)


def resolve_timezone(name: str | None) -> ZoneInfo:
    """Return the named zone, or raise CronError naming what was wrong."""
    if not name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise CronError(f"Unknown time zone: {name}") from exc


def next_fire_after(
    expression: str,
    after: datetime,
    *,
    timezone: str | None = "UTC",
) -> datetime:
    """The first firing strictly after ``after``, returned in UTC.

    Matching happens in the schedule's own zone, so "every day at 02:00" stays
    at 02:00 local across a daylight-saving change rather than drifting by an
    hour. A local time that a spring-forward skips simply does not occur that
    day; the next matching minute is found instead. A local time that autumn
    repeats fires on the first pass, because the candidate minutes are walked
    forward and the first match wins.
    """
    cron = parse(expression)
    zone = resolve_timezone(timezone)

    moment = after.astimezone(zone) if after.tzinfo else after.replace(tzinfo=UTC).astimezone(zone)
    # Start from the next whole minute: a schedule never fires twice in one.
    moment = (moment + timedelta(minutes=1)).replace(second=0, microsecond=0)

    limit = moment + timedelta(days=MAX_LOOKAHEAD_DAYS)
    while moment <= limit:
        if cron.matches(moment):
            return moment.astimezone(UTC)
        moment += timedelta(minutes=1)

    raise CronError(f"{cron.expression!r} has no firing within four years")
