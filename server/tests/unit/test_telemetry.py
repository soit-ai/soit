"""Opt-in anonymous telemetry: one report a day, with only the documented fields."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.entitlements.edition import EditionState
from app.kernel.entitlements.license import LicenseState, LicenseStatus
from app.kernel.observe.telemetry import build_report, daily_usage, installation_id
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.db.models.usage import UsageDailyAggregate
from app.wiring.telemetry import preview_report, report_day, send_daily_report

NOW = datetime(2026, 9, 29, 3, 0, tzinfo=UTC)
DAY = date(2026, 9, 28)
SETTINGS = SimpleNamespace(
    platform_version="1.3.0",
    environment="Production",
    soit_role="all",
    vector_backend="pgvector",
    storage_url="file:///data/storage",
    secrets_backend="sealed",
    telemetry_enabled=True,
    telemetry_endpoint="https://soit.ai/api/telemetry",
)
EDITION = EditionState(
    edition="community",
    license=LicenseState(LicenseStatus.ABSENT),
    enabled_features=frozenset({"workflow.runtime", "agent.runtime"}),
)


class _Sink:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.reports: list[dict[str, Any]] = []

    async def send(self, report: dict[str, Any]) -> None:
        if self.error is not None:
            raise self.error
        self.reports.append(report)


def _factory(async_db: AsyncSession) -> Any:
    return async_sessionmaker(bind=async_db.bind, class_=AsyncSession, expire_on_commit=False)


async def _seed(async_db: AsyncSession) -> None:
    moment = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
    for index, (source, parent) in enumerate(
        [("platform", None), ("gateway", None), ("gateway", None), ("platform", "run_parent")]
    ):
        async_db.add(
            Run(
                id=f"run_t{index}",
                tenant_id="tenant-secret-name",
                workspace_id="ws_1",
                user_id="u1",
                mode="gateway",
                status="succeeded",
                source=source,
                parent_run_id=parent,
                created_at=moment,
            )
        )
    async_db.add(Run(id="run_other_day", tenant_id="t", workspace_id="ws_1", user_id="u1", mode="agent", status="succeeded", created_at=moment - timedelta(days=1)))
    for workspace, user, calls in (("ws_1", "u1", 7), ("ws_2", "u2", 3), ("ws_2", "", 1)):
        async_db.add(
            UsageDailyAggregate(tenant_id="t", workspace_id=workspace, day=DAY, user_id=user, call_count=calls)
        )
    await async_db.commit()


def test_the_report_covers_the_last_complete_utc_day() -> None:
    assert report_day(NOW) == DAY


@pytest.mark.asyncio
async def test_the_installation_id_is_random_and_kept(async_db) -> None:
    first = await installation_id(async_db)
    assert len(first) == 36
    assert await installation_id(async_db) == first


@pytest.mark.asyncio
async def test_the_days_counts(async_db) -> None:
    await _seed(async_db)

    assert await daily_usage(async_db, DAY) == {
        "governed_runs": 3,  # top-level runs only; the child run is part of its parent
        "gateway_calls": 2,
        "metered_calls": 11,
        "active_workspaces": 2,
        "active_principals": 2,
    }


@pytest.mark.asyncio
async def test_the_report_holds_only_the_documented_fields(async_db) -> None:
    await _seed(async_db)

    report = await build_report(async_db, settings=SETTINGS, edition=EDITION, day=DAY)

    assert set(report) == {"schema", "installation_id", "version", "edition", "day", "deployment", "usage", "features"}
    assert report["schema"] == 1
    assert report["deployment"] == {
        "environment": "production",
        "role": "all",
        "vector_backend": "pgvector",
        "storage": "file",
        "secrets_backend": "sealed",
    }
    assert report["features"] == ["agent.runtime", "workflow.runtime"]
    # Nothing identifying the tenants, workspaces or users leaves.
    serialized = json.dumps(report)
    for private in ("tenant-secret-name", "ws_1", "ws_2", "u1", "u2", "/data/storage"):
        assert private not in serialized


@pytest.mark.asyncio
async def test_a_day_is_sent_once_whatever_the_number_of_processes(async_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.wiring.telemetry.current_edition", lambda: EDITION)
    sink = _Sink()
    factory = _factory(async_db)

    assert await send_daily_report(SETTINGS, factory, sink, now=NOW) is True
    assert await send_daily_report(SETTINGS, factory, sink, now=NOW) is False
    assert await send_daily_report(SETTINGS, factory, sink, now=NOW + timedelta(days=1)) is True

    assert [report["day"] for report in sink.reports] == ["2026-09-28", "2026-09-29"]
    assert sink.reports[0]["installation_id"] == sink.reports[1]["installation_id"]


@pytest.mark.asyncio
async def test_a_report_that_fails_to_go_out_is_tried_again(async_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.wiring.telemetry.current_edition", lambda: EDITION)
    factory = _factory(async_db)

    with pytest.raises(ConnectionError):
        await send_daily_report(SETTINGS, factory, _Sink(ConnectionError("offline")), now=NOW)
    sink = _Sink()
    assert await send_daily_report(SETTINGS, factory, sink, now=NOW) is True
    assert len(sink.reports) == 1


@pytest.mark.asyncio
async def test_the_preview_shows_the_report_and_whether_it_is_sent(async_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.wiring.telemetry.current_edition", lambda: EDITION)
    settings = SimpleNamespace(**{**vars(SETTINGS), "telemetry_enabled": False})

    preview = await preview_report(settings, async_db, now=NOW)

    assert preview["enabled"] is False
    assert preview["endpoint"] == "https://soit.ai/api/telemetry"
    assert preview["report"]["day"] == "2026-09-28"
