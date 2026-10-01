"""Evaluation datasets: revisions, snapshots, import, archive and scope."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.kernel.commons.errors import ConflictError, NotFoundError, ValidationError
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.evaluation.application.dataset_service import RegressionDatasetService
from app.modules.evaluation.application.service import (
    RegressionEvaluationService,
    RegressionRunResult,
)
from app.modules.evaluation.domain.models import RegressionCase

AGENT = "agt_ds"


def _case(name: str, term: str = "ok", **extra) -> dict:
    return {
        "name": name,
        "input": f"Question {name}",
        "expected_features": {"minimum_output_terms": [term]},
        **extra,
    }


async def _events(async_db, event_type: str | None = None) -> list[AuditEvent]:
    rows = (await async_db.exec(select(AuditEvent).order_by(AuditEvent.created_at))).all()
    events = [row[0] for row in rows]
    return [event for event in events if event_type is None or event.event_type == event_type]


@pytest.mark.asyncio
async def test_a_new_dataset_starts_at_revision_one_with_an_empty_snapshot(async_db, ctx) -> None:
    service = RegressionDatasetService(db=async_db, ctx=ctx)

    dataset = await service.create_dataset(
        subject_kind="agent", subject_id=AGENT, name="refunds", description=" policy cases "
    )

    assert (dataset.revision, dataset.status, dataset.description) == (1, "active", "policy cases")
    versions = await service.list_versions(dataset)
    assert [(v.revision, v.case_count) for v in versions] == [(1, 0)]
    assert versions[0].snapshot_json == []
    assert [e.event_type for e in await _events(async_db)] == ["evaluation.dataset.created"]


@pytest.mark.asyncio
async def test_dataset_names_are_unique_per_agent(async_db, ctx) -> None:
    service = RegressionDatasetService(db=async_db, ctx=ctx)
    await service.create_dataset(subject_kind="agent", subject_id=AGENT, name="refunds")

    with pytest.raises(ConflictError):
        await service.create_dataset(subject_kind="agent", subject_id=AGENT, name=" refunds ")
    other = await service.create_dataset(subject_kind="agent", subject_id="agt_other", name="refunds")
    assert other.subject_id == "agt_other"
    with pytest.raises(ValidationError):
        await service.create_dataset(subject_kind="agent", subject_id=AGENT, name="  ")


@pytest.mark.asyncio
async def test_every_case_change_advances_the_revision_and_snapshots_the_set(async_db, ctx) -> None:
    service = RegressionDatasetService(db=async_db, ctx=ctx)
    dataset = await service.create_dataset(subject_kind="agent", subject_id=AGENT, name="refunds")

    first = await service.add_case(dataset.id, _case("one"))
    second = await service.add_case(dataset.id, _case("two"), note="second case")
    assert (first.dataset_revision, second.dataset_revision) == (2, 3)

    edited = await service.update_case(
        dataset.id, first.id, {"expected_features": {"minimum_output_terms": ["changed"]}}
    )
    assert edited.id == first.id and edited.dataset_revision == 4
    assert second.dataset_revision == 3

    await service.remove_case(dataset.id, second.id)
    refreshed = await service.get_dataset(dataset.id)
    assert refreshed.revision == 5

    versions = await service.list_versions(refreshed)
    assert [v.revision for v in versions] == [5, 4, 3, 2, 1]
    assert [v.case_count for v in versions] == [1, 2, 2, 1, 0]
    assert [v.changes_json for v in versions[:3]] == [
        {"added": 0, "removed": 1, "changed": 0},
        {"added": 0, "removed": 0, "changed": 1},
        {"added": 1, "removed": 0, "changed": 0},
    ]
    assert versions[2].note == "second case"
    assert len({v.content_hash for v in versions}) == 5

    third = await service.get_version(refreshed, 3)
    assert [item["name"] for item in third.snapshot_json] == ["one", "two"]
    assert third.snapshot_json[0]["expected_features"] == {"minimum_output_terms": ["ok"]}

    events = [e.event_type for e in await _events(async_db)]
    assert events == [
        "evaluation.dataset.created",
        "evaluation.case.created",
        "evaluation.case.created",
        "evaluation.case.updated",
        "evaluation.case.removed",
    ]


@pytest.mark.asyncio
async def test_a_removed_case_leaves_the_set_but_its_row_stays(async_db, ctx) -> None:
    service = RegressionDatasetService(db=async_db, ctx=ctx)
    dataset = await service.create_dataset(subject_kind="agent", subject_id=AGENT, name="refunds")
    case = await service.add_case(dataset.id, _case("one"))

    await service.remove_case(dataset.id, case.id)

    dataset = await service.get_dataset(dataset.id)
    assert await service.list_cases(dataset) == []
    assert await service.count_cases(dataset) == 0
    with pytest.raises(NotFoundError):
        await service.get_case(dataset, case.id)
    row = (await async_db.exec(select(RegressionCase).where(RegressionCase.id == case.id))).first()[0]
    assert row.status == "removed"
    # The name is free again once the case is gone.
    await service.add_case(dataset.id, _case("one"))


@pytest.mark.asyncio
async def test_case_names_are_unique_and_edits_are_validated(async_db, ctx) -> None:
    service = RegressionDatasetService(db=async_db, ctx=ctx)
    dataset = await service.create_dataset(subject_kind="agent", subject_id=AGENT, name="refunds")
    one = await service.add_case(dataset.id, _case("one"))
    await service.add_case(dataset.id, _case("two"))

    with pytest.raises(ConflictError):
        await service.add_case(dataset.id, _case("one"))
    with pytest.raises(ConflictError):
        await service.update_case(dataset.id, one.id, {"name": "two"})
    with pytest.raises(ValidationError):
        await service.update_case(dataset.id, one.id, {"expected_features": {}})
    with pytest.raises(ValidationError):
        await service.add_case(dataset.id, {"name": "x", "input": "y", "expected_features": {"nope": 1}})

    unchanged = await service.update_case(dataset.id, one.id, {"name": "one"})
    assert unchanged.dataset_revision == 2
    assert (await service.get_dataset(dataset.id)).revision == 3


@pytest.mark.asyncio
async def test_import_is_all_or_nothing(async_db, ctx) -> None:
    service = RegressionDatasetService(db=async_db, ctx=ctx)
    dataset = await service.create_dataset(subject_kind="agent", subject_id=AGENT, name="refunds")
    good = json.dumps(_case("fresh"))
    bad = json.dumps({"name": "broken", "input": "x"})

    with pytest.raises(ValidationError) as caught:
        await service.import_cases(dataset.id, f"{good}\n{bad}\n")

    assert [item["line"] for item in caught.value.details["errors"]] == [2]
    dataset = await service.get_dataset(dataset.id)
    assert dataset.revision == 1
    assert await service.count_cases(dataset) == 0

    imported, count = await service.import_cases(dataset.id, f"{good}\n{json.dumps(_case('other'))}\n")
    assert count == 2 and imported.revision == 2
    stamped = {case.dataset_revision for case in await service.list_cases(imported)}
    assert stamped == {2}
    versions = await service.list_versions(imported)
    assert versions[0].case_count == 2 and versions[0].note == "Imported from JSONL"
    assert [e.event_type for e in await _events(async_db, "evaluation.dataset.imported")] == [
        "evaluation.dataset.imported"
    ]

    with pytest.raises(ConflictError):
        await service.import_cases(dataset.id, good)
    assert (await service.get_dataset(dataset.id)).revision == 2


@pytest.mark.asyncio
async def test_an_export_imports_back_into_another_dataset_unchanged(async_db, ctx) -> None:
    service = RegressionDatasetService(db=async_db, ctx=ctx)
    source = await service.create_dataset(subject_kind="agent", subject_id=AGENT, name="source")
    await service.add_case(source.id, _case("text"))
    await service.add_case(
        source.id,
        {
            "name": "messages",
            "input": {"messages": [{"role": "user", "content": "café?"}]},
            "expected_features": {"max_latency_ms": 900, "llm_judge": {"rubric": "Polite"}},
        },
    )
    _, exported = await service.export_cases(source.id)
    copy = await service.create_dataset(subject_kind="agent", subject_id="agt_copy", name="copy")

    await service.import_cases(copy.id, exported)

    _, again = await service.export_cases(copy.id)
    assert again == exported
    first = await service.get_version(await service.get_dataset(source.id), 3)
    second = await service.get_version(await service.get_dataset(copy.id), 2)
    assert first.content_hash == second.content_hash
    assert len(await _events(async_db, "evaluation.dataset.exported")) == 2


@pytest.mark.asyncio
async def test_archiving_takes_cases_out_of_every_run_and_restoring_puts_them_back(async_db, ctx) -> None:
    service = RegressionDatasetService(db=async_db, ctx=ctx)
    evaluation = RegressionEvaluationService(db=async_db, ctx=ctx)
    dataset = await service.create_dataset(subject_kind="agent", subject_id=AGENT, name="refunds")
    kept = await service.add_case(dataset.id, _case("kept"))
    gone = await service.add_case(dataset.id, _case("gone"))
    await service.remove_case(dataset.id, gone.id)

    archived = await service.update_dataset(dataset.id, status="archived")

    revision = archived.revision
    assert archived.status == "archived"
    assert await evaluation.list_cases(subject_kind="agent", subject_id=AGENT) == []
    with pytest.raises(ValidationError):
        await service.add_case(dataset.id, _case("late"))

    restored = await service.update_dataset(dataset.id, status="active", description="back")

    assert restored.revision == revision
    assert [case.id for case in await evaluation.list_cases(subject_kind="agent", subject_id=AGENT)] == [kept.id]
    assert [e.event_type for e in await _events(async_db)][-2:] == [
        "evaluation.dataset.archived",
        "evaluation.dataset.restored",
    ]


@pytest.mark.asyncio
async def test_the_dataset_revision_is_what_a_run_records_even_after_a_removal(async_db, ctx) -> None:
    """Removing a case lowers no case's revision, so only the dataset row can show it."""
    service = RegressionDatasetService(db=async_db, ctx=ctx)
    evaluation = RegressionEvaluationService(db=async_db, ctx=ctx)
    dataset = await service.create_dataset(subject_kind="agent", subject_id=AGENT, name="default")
    keep = await service.add_case(dataset.id, _case("keep"))
    drop = await service.add_case(dataset.id, _case("drop"))

    async def runner(_case) -> RegressionRunResult:
        return RegressionRunResult(output="ok", latency_ms=1, cost={"amount": 0})

    first = await evaluation.evaluate_subject_version(
        subject_kind="agent", subject_id=AGENT, subject_version_id="v1", runner=runner
    )
    assert first.summary["dataset_revision"] == 3 and first.summary["total"] == 2
    await service.remove_case(dataset.id, drop.id)
    second = await evaluation.evaluate_subject_version(
        subject_kind="agent", subject_id=AGENT, subject_version_id="v2", runner=runner
    )

    assert second.summary["dataset_revision"] == 4
    assert second.summary["baseline_report_id"] is None
    third = await evaluation.evaluate_subject_version(
        subject_kind="agent", subject_id=AGENT, subject_version_id="v3", runner=runner
    )
    assert third.summary["baseline_report_id"] == second.report_id
    assert keep.id in {item["case_id"] for item in third.cases}


@pytest.mark.asyncio
async def test_creating_a_dataset_takes_over_cases_already_filed_under_its_name(async_db, ctx) -> None:
    for name, revision in (("old-a", 1), ("old-b", 3)):
        async_db.add(
            RegressionCase(
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                subject_kind="agent",
                subject_id=AGENT,
                source_run_id=f"run_{name}",
                name=name,
                dataset="legacy",
                dataset_revision=revision,
                input_snapshot_json={"input": name},
                expected_features_json={"minimum_output_terms": ["x"]},
            )
        )
    await async_db.commit()
    service = RegressionDatasetService(db=async_db, ctx=ctx)

    dataset = await service.create_dataset(subject_kind="agent", subject_id=AGENT, name="legacy")

    assert dataset.revision == 3
    versions = await service.list_versions(dataset)
    assert (versions[0].case_count, versions[0].note) == (2, "Took over existing cases")
    assert await service.count_cases(dataset) == 2


@pytest.mark.asyncio
async def test_a_case_frozen_from_a_run_files_into_the_default_dataset(async_db, ctx) -> None:
    run = await TraceWriter(async_db, ctx).create_run(
        mode="agent",
        subject_kind="agent",
        subject_id=AGENT,
        subject_version_id="v1",
        input_summary=json.dumps({"messages": [{"role": "user", "content": "refund?"}]}),
    )
    evaluation = RegressionEvaluationService(db=async_db, ctx=ctx)
    datasets = evaluation.datasets

    first = await evaluation.create_case_from_run(
        run_id=run.id, name="first", expected_features={"minimum_output_terms": ["a"]}
    )
    second = await evaluation.create_case_from_run(
        run_id=run.id, name="second", expected_features={"minimum_output_terms": ["b"]}
    )

    assert (first.dataset_revision, second.dataset_revision) == (1, 2)
    dataset = await datasets.find_dataset(subject_kind="agent", subject_id=AGENT, name="default")
    assert dataset is not None and dataset.revision == 2
    assert [v.case_count for v in await datasets.list_versions(dataset)] == [2, 1]
    assert first.source_run_id == run.id


@pytest.mark.asyncio
async def test_datasets_cases_versions_and_reports_are_scoped_to_the_workspace(
    async_db, tenant1_ctx, tenant2_ctx
) -> None:
    one = RegressionDatasetService(db=async_db, ctx=tenant1_ctx)
    two = RegressionDatasetService(db=async_db, ctx=tenant2_ctx)
    dataset = await one.create_dataset(subject_kind="agent", subject_id=AGENT, name="refunds")
    case = await one.add_case(dataset.id, _case("one"))

    assert await two.list_datasets() == []
    with pytest.raises(NotFoundError):
        await two.get_dataset(dataset.id)
    with pytest.raises(NotFoundError):
        await two.update_dataset(dataset.id, status="archived")
    with pytest.raises(NotFoundError):
        await two.add_case(dataset.id, _case("two"))
    with pytest.raises(NotFoundError):
        await two.export_cases(dataset.id)
    with pytest.raises(NotFoundError):
        await two.import_cases(dataset.id, json.dumps(_case("x")))
    with pytest.raises(NotFoundError):
        await two.remove_case(dataset.id, case.id)

    # The same name is free in another tenant, and its cases are its own.
    mine = await two.create_dataset(subject_kind="agent", subject_id=AGENT, name="refunds")
    assert mine.id != dataset.id and await two.count_cases(mine) == 0
    assert (await one.get_dataset(dataset.id)).revision == 2


@pytest.mark.asyncio
async def test_datasets_list_shows_case_counts_and_the_latest_report(async_db, ctx) -> None:
    service = RegressionDatasetService(db=async_db, ctx=ctx)
    evaluation = RegressionEvaluationService(db=async_db, ctx=ctx)
    dataset = await service.create_dataset(subject_kind="agent", subject_id=AGENT, name="default")
    await service.add_case(dataset.id, _case("one"))
    await service.add_case(dataset.id, _case("two", term="never"))

    async def runner(_case) -> RegressionRunResult:
        return RegressionRunResult(output="ok", latency_ms=1, cost={"amount": 0})

    result = await evaluation.evaluate_subject_version(
        subject_kind="agent", subject_id=AGENT, subject_version_id="v1", runner=runner
    )

    [summary] = await service.list_datasets(subject_id=AGENT)

    assert summary.case_count == 2
    assert summary.latest_report is not None and summary.latest_report.id == result.report_id
    assert summary.latest_report.passed is False
    assert await service.list_datasets(status="archived") == []
