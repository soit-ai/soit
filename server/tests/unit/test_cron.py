"""test_cron

Covers the parts of cron that catch people out: how day-of-month combines with
day-of-week, and what happens to a local time a daylight-saving change skips or
repeats. The rest is arithmetic.
"""

from datetime import UTC, datetime

import pytest

from app.kernel.runtime.schedules.cron import CronError, next_fire_after, parse

NOON = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def test_the_next_firing_is_strictly_after_the_moment_given():
    """A schedule that just fired must not fire again for the same minute."""
    on_the_hour = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)

    assert next_fire_after("0 * * * *", on_the_hour) == datetime(
        2026, 8, 30, 13, 0, tzinfo=UTC
    )


def test_lists_ranges_and_steps_all_parse():
    assert next_fire_after("*/15 * * * *", datetime(2026, 8, 30, 12, 1, tzinfo=UTC)) == (
        datetime(2026, 8, 30, 12, 15, tzinfo=UTC)
    )
    assert next_fire_after("0 9,17 * * *", datetime(2026, 8, 30, 12, 0, tzinfo=UTC)) == (
        datetime(2026, 8, 30, 17, 0, tzinfo=UTC)
    )
    assert next_fire_after("0 0 * * 1-5", datetime(2026, 8, 29, 12, 0, tzinfo=UTC)) == (
        # 29 August 2026 is a Saturday, so the next weekday midnight is Monday.
        datetime(2026, 8, 31, 0, 0, tzinfo=UTC)
    )


def test_sunday_is_both_zero_and_seven():
    """Crontabs in the wild use either; refusing one would surprise people."""
    as_zero = next_fire_after("0 4 * * 0", NOON)
    as_seven = next_fire_after("0 4 * * 7", NOON)

    assert as_zero == as_seven
    assert as_zero.weekday() == 6


def test_day_of_month_and_day_of_week_are_ored_when_both_are_restricted():
    """What "the first of the month, and every Monday" has always meant."""
    # 1 September 2026 is a Tuesday; the Monday before it is 31 August.
    assert next_fire_after("0 2 1 * 1", datetime(2026, 8, 30, 12, 0, tzinfo=UTC)) == (
        datetime(2026, 8, 31, 2, 0, tzinfo=UTC)
    )
    # With only the day restricted, the Monday does not count.
    assert next_fire_after("0 2 1 * *", datetime(2026, 8, 30, 12, 0, tzinfo=UTC)) == (
        datetime(2026, 9, 1, 2, 0, tzinfo=UTC)
    )


def test_a_daily_time_keeps_its_local_hour_across_a_clock_change():
    """02:00 local stays 02:00 local; in UTC it moves by an hour, as it should."""
    # Europe/Berlin leaves summer time on 25 October 2026.
    before = next_fire_after(
        "0 3 * * *", datetime(2026, 10, 23, 12, 0, tzinfo=UTC), timezone="Europe/Berlin"
    )
    after = next_fire_after(
        "0 3 * * *", datetime(2026, 10, 26, 12, 0, tzinfo=UTC), timezone="Europe/Berlin"
    )

    assert before.hour == 1  # 03:00 CEST
    assert after.hour == 2  # 03:00 CET


def test_a_local_time_the_clock_skips_simply_does_not_fire_that_day():
    """Spring forward removes 02:30 entirely; the schedule waits a day."""
    # Europe/Berlin springs forward on 29 March 2026: 02:00 to 03:00 vanishes.
    fire = next_fire_after(
        "30 2 * * *", datetime(2026, 3, 28, 12, 0, tzinfo=UTC), timezone="Europe/Berlin"
    )

    assert fire.date().isoformat() == "2026-03-29"
    # It is not the 29th at 02:30 local, because that minute does not exist.
    assert fire.astimezone(UTC) == datetime(2026, 3, 29, 1, 30, tzinfo=UTC)


def test_an_unparseable_expression_is_refused_at_parse_time():
    for bad in ("", "* * * *", "* * * * * *", "61 * * * *", "* 25 * * *", "5-1 * * * *"):
        with pytest.raises(CronError):
            parse(bad)


def test_an_unknown_timezone_is_named_in_the_error():
    with pytest.raises(CronError, match="Nowhere/Special"):
        next_fire_after("0 * * * *", NOON, timezone="Nowhere/Special")


def test_a_naive_moment_is_read_as_utc():
    """Callers pass stored timestamps, which may come back without a zone."""
    assert next_fire_after("0 * * * *", datetime(2026, 8, 30, 12, 30)) == (
        datetime(2026, 8, 30, 13, 0, tzinfo=UTC)
    )


def test_february_29_is_found_rather_than_giving_up():
    assert next_fire_after("0 0 29 2 *", datetime(2026, 3, 1, 0, 0, tzinfo=UTC)) == (
        datetime(2028, 2, 29, 0, 0, tzinfo=UTC)
    )
