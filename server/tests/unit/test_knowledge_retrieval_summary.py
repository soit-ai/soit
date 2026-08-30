"""test_knowledge_retrieval_summary

Retrieval quality is read from the run ledger every query already writes, so
these cover the aggregation rather than any new recording path.
"""

from datetime import timedelta

from app.kernel.commons.ids import generate_run_id
from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.runs import Run, RunStep
from app.modules.knowledge.application.schemas import KnowledgeRetrievalSummary


def _record_query(db, ctx, knowledge_id: str, *, metrics: dict, age_hours: int = 1) -> None:
    """Write the run and retrieval step a knowledge query leaves behind."""
    run_id = generate_run_id()
    started = utc_now() - timedelta(hours=age_hours)
    db.add(
        Run(
            id=run_id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            trace_id=f"trace_{run_id}",
            mode="knowledge_query",
            kind="tool",
            subject_kind="knowledge",
            subject_id=knowledge_id,
            status="succeeded",
            started_at=started,
        )
    )
    db.add(
        RunStep(
            id=f"step_{run_id}",
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            run_id=run_id,
            step_type="retrieval",
            status="succeeded",
            started_at=started,
            metrics_json=metrics,
        )
    )
    db.commit()


def _summarize(db, ctx, knowledge_id: str, **kwargs) -> KnowledgeRetrievalSummary:
    from app.modules.knowledge.application.service import KnowledgeService

    service = KnowledgeService.__new__(KnowledgeService)
    service.db = db
    service.ctx = ctx
    return KnowledgeService.summarize_retrieval(service, knowledge_id, **kwargs)


def test_hit_and_zero_hit_rates_come_from_recorded_query_steps(db, ctx):
    _record_query(db, ctx, "knw_1", metrics={"result_count": 4, "max_score": 0.81})
    _record_query(db, ctx, "knw_1", metrics={"result_count": 2, "max_score": 0.62})
    _record_query(db, ctx, "knw_1", metrics={"result_count": 3, "max_score": 0.31})
    _record_query(db, ctx, "knw_1", metrics={"result_count": 0})

    summary = _summarize(db, ctx, "knw_1")

    assert summary.queries == 4
    assert summary.hits == 2
    assert summary.zero_hits == 1
    assert summary.hit_rate == 0.5
    assert summary.zero_hit_rate == 0.25


def test_a_window_with_no_queries_reports_no_rate(db, ctx):
    """Zero would read as "every query missed" rather than "nobody asked"."""
    summary = _summarize(db, ctx, "knw_empty")

    assert summary.queries == 0
    assert summary.hit_rate is None
    assert summary.zero_hit_rate is None


def test_another_knowledge_base_is_not_counted(db, ctx):
    _record_query(db, ctx, "knw_1", metrics={"result_count": 1, "max_score": 0.9})
    _record_query(db, ctx, "knw_2", metrics={"result_count": 1, "max_score": 0.9})

    assert _summarize(db, ctx, "knw_1").queries == 1


def test_the_window_bounds_which_queries_are_counted(db, ctx):
    _record_query(db, ctx, "knw_1", metrics={"result_count": 1, "max_score": 0.9}, age_hours=1)
    _record_query(db, ctx, "knw_1", metrics={"result_count": 1, "max_score": 0.9}, age_hours=48)

    summary = _summarize(db, ctx, "knw_1", since=utc_now() - timedelta(hours=24))

    assert summary.queries == 1


def test_the_threshold_is_reported_with_the_rate_it_produced(db, ctx):
    """Scores mean different things per strategy, so the bar is never implied."""
    _record_query(db, ctx, "knw_1", metrics={"result_count": 1, "max_score": 0.55})

    default = _summarize(db, ctx, "knw_1")
    lenient = _summarize(db, ctx, "knw_1", score_threshold=0.5)

    assert default.hits == 0
    assert default.score_threshold == 0.6
    assert lenient.hits == 1
    assert lenient.score_threshold == 0.5
