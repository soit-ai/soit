"""Transaction-boundary tests for response persistence repositories."""

from sqlmodel import Session

from app.kernel.runtime.db.models.responses import Response, ResponseEvent
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)


def test_response_and_events_rollback_as_one_unit(db, tenant1_ctx) -> None:
    response_repo = ResponseRepository(db, tenant1_ctx)
    event_repo = ResponseEventRepository(db, tenant1_ctx)
    response = response_repo.create(Response(status="queued"))
    event = event_repo.create(
        ResponseEvent(
            response_id=response.id,
            sequence=1,
            type="response.created",
        )
    )

    db.rollback()

    check = Session(db.get_bind())
    try:
        assert check.get(Response, response.id) is None
        assert check.get(ResponseEvent, event.id) is None
    finally:
        check.close()


def test_response_update_can_be_rolled_back(db, tenant1_ctx) -> None:
    response_repo = ResponseRepository(db, tenant1_ctx)
    response = response_repo.create(Response(status="queued"))
    db.commit()

    response.status = "completed"
    response_repo.update(response)
    db.rollback()

    db.expire_all()
    assert response_repo.require(response.id).status == "queued"
