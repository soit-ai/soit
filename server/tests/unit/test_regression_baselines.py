"""A regression report must actually identify regressions.

Reporting current failures alone cannot distinguish a case this change broke
from one that never worked. The first is a reason to stop a release; the second
is a known gap.
"""

from app.kernel.contracts.context import RequestContext
from app.modules.evaluation.application.service import RegressionEvaluationService
from app.modules.evaluation.domain.models import RegressionCase, RegressionReport


def _service(db, ctx: RequestContext) -> RegressionEvaluationService:
    return RegressionEvaluationService(db=db, ctx=ctx)


def _case(db, ctx, *, case_id: str, dataset: str = "default", revision: int = 1):
    case = RegressionCase(
        id=case_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        subject_kind="agent",
        subject_id="agt_1",
        source_run_id=f"run_{case_id}",
        name=case_id,
        dataset=dataset,
        dataset_revision=revision,
    )
    db.add(case)
    db.commit()
    return case


def _report(db, ctx, *, report_id: str, results: list[dict], dataset="default", revision=1):
    report = RegressionReport(
        id=report_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        subject_kind="agent",
        subject_id="agt_1",
        subject_version_id="ver_1",
        dataset=dataset,
        dataset_revision=revision,
        passed=all(item["passed"] for item in results),
        case_results_json=results,
    )
    db.add(report)
    db.commit()
    return report


def test_a_case_that_used_to_pass_is_reported_as_a_regression(db, ctx):
    baseline = _report(
        db,
        ctx,
        report_id="regrep_base",
        results=[{"case_id": "a", "passed": True}, {"case_id": "b", "passed": False}],
    )
    current = [{"case_id": "a", "passed": False}, {"case_id": "b", "passed": False}]

    regressed, fixed = _service(db, ctx).compare_to_baseline(current, baseline)

    # "b" never passed, so it is a known gap; only "a" is something that broke.
    assert regressed == ["a"]
    assert fixed == []


def test_a_case_that_started_passing_is_reported_as_fixed(db, ctx):
    baseline = _report(
        db,
        ctx,
        report_id="regrep_base",
        results=[{"case_id": "a", "passed": False}],
    )

    regressed, fixed = _service(db, ctx).compare_to_baseline(
        [{"case_id": "a", "passed": True}], baseline
    )

    assert regressed == []
    assert fixed == ["a"]


def test_a_case_absent_from_the_baseline_is_neither(db, ctx):
    baseline = _report(
        db, ctx, report_id="regrep_base", results=[{"case_id": "a", "passed": True}]
    )

    regressed, fixed = _service(db, ctx).compare_to_baseline(
        [{"case_id": "a", "passed": True}, {"case_id": "new", "passed": False}],
        baseline,
    )

    # A brand new case failing is not a regression; nothing broke.
    assert regressed == []
    assert fixed == []


def test_without_a_baseline_nothing_is_called_a_regression(db, ctx):
    regressed, fixed = _service(db, ctx).compare_to_baseline(
        [{"case_id": "a", "passed": False}], None
    )

    assert regressed == []
    assert fixed == []


def test_the_dataset_revision_follows_the_highest_case_revision(db, ctx):
    service = _service(db, ctx)
    _case(db, ctx, case_id="a", revision=1)
    _case(db, ctx, case_id="b", revision=3)

    cases = service.list_cases(subject_kind="agent", subject_id="agt_1")

    assert service.dataset_revision(cases) == 3


def test_a_baseline_from_a_different_revision_is_not_used(db, ctx):
    service = _service(db, ctx)
    _report(db, ctx, report_id="regrep_old", results=[], revision=1)

    baseline = service.find_baseline(
        subject_kind="agent",
        subject_id="agt_1",
        dataset="default",
        dataset_revision=2,
    )

    # Comparing across revisions would attribute a change in the case set to a
    # change in quality.
    assert baseline is None


def test_a_baseline_from_another_dataset_is_not_used(db, ctx):
    service = _service(db, ctx)
    _report(db, ctx, report_id="regrep_other", results=[], dataset="smoke")

    assert (
        service.find_baseline(
            subject_kind="agent",
            subject_id="agt_1",
            dataset="default",
            dataset_revision=1,
        )
        is None
    )


def test_the_most_recent_comparable_report_is_the_baseline(db, ctx):
    service = _service(db, ctx)
    _report(db, ctx, report_id="regrep_1", results=[{"case_id": "a", "passed": True}])
    newer = _report(
        db, ctx, report_id="regrep_2", results=[{"case_id": "a", "passed": False}]
    )

    baseline = service.find_baseline(
        subject_kind="agent",
        subject_id="agt_1",
        dataset="default",
        dataset_revision=1,
    )

    assert baseline is not None and baseline.id == newer.id


def test_cases_are_listed_per_dataset(db, ctx):
    service = _service(db, ctx)
    _case(db, ctx, case_id="a", dataset="default")
    _case(db, ctx, case_id="b", dataset="smoke")

    default_cases = service.list_cases(
        subject_kind="agent", subject_id="agt_1", dataset="default"
    )
    all_cases = service.list_cases(subject_kind="agent", subject_id="agt_1")

    # Unrelated suites must not silently evaluate each other's cases.
    assert [case.id for case in default_cases] == ["a"]
    assert len(all_cases) == 2
