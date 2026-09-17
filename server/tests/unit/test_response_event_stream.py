"""Tests for replay-and-tail response event streaming."""

from types import SimpleNamespace

import pytest

from app.kernel.runtime.responses.streaming import tail_response_events


class _FakeDb:
    def __init__(self) -> None:
        self.releases = 0

    def expire_all(self) -> None:
        return None

    async def rollback(self) -> None:
        self.releases += 1


class _FakeResponseService:
    def __init__(self) -> None:
        self.db = _FakeDb()
        self.trace_writer = SimpleNamespace(event_bus=None)
        self._status_reads = 0
        self._events = [
            SimpleNamespace(
                response_id="resp_test",
                sequence=1,
                source="ag-ui",
                type="RUN_STARTED",
                payload_json={"type": "RUN_STARTED", "threadId": "thread", "runId": "run"},
            )
        ]

    async def list_response_events(self, response_id, *, limit, offset, after_sequence=None):
        assert response_id == "resp_test"
        assert limit == 1000
        assert offset == 0
        cursor = after_sequence or 0
        return [event for event in self._events if event.sequence > cursor]

    async def get_response(self, response_id):
        assert response_id == "resp_test"
        self._status_reads += 1
        status = "running" if self._status_reads == 1 else "succeeded"
        return SimpleNamespace(status=status)


@pytest.mark.asyncio
async def test_tail_response_events_replays_heartbeats_and_closes_at_terminal_status():
    items = []
    async for item in tail_response_events(
        _FakeResponseService(),
        "resp_test",
        after_sequence=0,
        heartbeat_seconds=0,
        poll_interval_seconds=0,
    ):
        items.append(item)

    assert [item["kind"] for item in items] == ["event", "heartbeat", "done"]
    assert items[0]["event"].sequence == 1


class _AgUiTerminalWindowService(_FakeResponseService):
    def __init__(self) -> None:
        super().__init__()
        self._event_reads = 0
        self._interaction_reads = 0

    async def list_response_events(self, response_id, *, limit, offset, after_sequence=None):
        self._event_reads += 1
        events = list(self._events)
        if self._event_reads >= 2:
            events.append(
                SimpleNamespace(
                    response_id="resp_test",
                    sequence=2,
                    source="ag-ui",
                    type="RUN_FINISHED",
                    payload_json={"type": "RUN_FINISHED", "threadId": "thread", "runId": "run"},
                )
            )
        cursor = after_sequence or 0
        return [event for event in events if event.sequence > cursor]

    async def get_response(self, response_id):
        return SimpleNamespace(
            status="succeeded",
            metadata_json={"interaction_id": "run"},
        )

    async def get_interaction(self, interaction_id):
        assert interaction_id == "run"
        self._interaction_reads += 1
        return SimpleNamespace(
            status="running" if self._interaction_reads == 1 else "succeeded"
        )


@pytest.mark.asyncio
async def test_agui_tail_waits_for_interaction_terminal_before_closing():
    items = []
    async for item in tail_response_events(
        _AgUiTerminalWindowService(),
        "resp_test",
        heartbeat_seconds=0,
        poll_interval_seconds=0,
    ):
        items.append(item)

    assert [item["kind"] for item in items] == ["event", "heartbeat", "event", "done"]
    assert items[2]["event"].type == "RUN_FINISHED"


class _SegmentedResponseService(_FakeResponseService):
    def __init__(self) -> None:
        super().__init__()
        self._events = [
            SimpleNamespace(
                response_id="resp_test",
                interaction_id="interaction_parent",
                sequence=1,
                source="ag-ui",
                type="RUN_STARTED",
                payload_json={"type": "RUN_STARTED", "runId": "interaction_parent"},
            ),
            SimpleNamespace(
                response_id="resp_test",
                interaction_id="interaction_child",
                sequence=5,
                source="ag-ui",
                type="RUN_FINISHED",
                payload_json={"type": "RUN_FINISHED", "runId": "interaction_child"},
            ),
        ]

    async def list_response_events(
        self,
        response_id,
        *,
        limit,
        offset,
        after_sequence=None,
        interaction_id=None,
    ):
        cursor = after_sequence or 0
        return [
            event
            for event in self._events
            if event.sequence > cursor and event.interaction_id == interaction_id
        ]

    async def get_response(self, response_id):
        return SimpleNamespace(
            status="succeeded",
            metadata_json={"interaction_id": "interaction_parent"},
        )

    async def get_interaction(self, interaction_id):
        assert interaction_id == "interaction_child"
        return SimpleNamespace(status="succeeded")


@pytest.mark.asyncio
async def test_agui_tail_replays_only_the_claimed_interaction_segment():
    items = []
    async for item in tail_response_events(
        _SegmentedResponseService(),
        "resp_test",
        interaction_id="interaction_child",
        heartbeat_seconds=0,
        poll_interval_seconds=0,
    ):
        items.append(item)

    assert [item["kind"] for item in items] == ["event", "done"]
    assert items[0]["event"].interaction_id == "interaction_child"


class _WaitingTwiceService(_FakeResponseService):
    """Reports running for two polls, then succeeded."""

    async def get_response(self, response_id):
        self._status_reads += 1
        return SimpleNamespace(status="running" if self._status_reads <= 2 else "succeeded")


@pytest.mark.asyncio
async def test_tail_releases_its_read_transaction_before_every_wait():
    # A tailer that waits with its SELECT's transaction open would pin one
    # pooled connection per open stream for the whole execution.
    service = _WaitingTwiceService()
    async for _ in tail_response_events(
        service, "resp_test", heartbeat_seconds=0, poll_interval_seconds=0
    ):
        pass

    assert service.db.releases == 2


class _ClaimedThenBoundService:
    """An interaction the worker binds a response to on the third poll."""

    def __init__(self) -> None:
        self.db = _FakeDb()
        self.trace_writer = SimpleNamespace(event_bus=None)
        self.ctx = SimpleNamespace(tenant_id="t", workspace_id="w")
        self.polls = 0

    async def get_interaction(self, interaction_id):
        self.polls += 1
        return SimpleNamespace(
            interaction_id=interaction_id,
            response_id="resp_test" if self.polls >= 3 else None,
            status="succeeded" if self.polls >= 3 else "queued",
        )

    async def list_response_events(self, response_id, **kwargs):
        return []

    async def get_response(self, response_id):
        return SimpleNamespace(status="succeeded", metadata_json={})


@pytest.mark.asyncio
async def test_claimed_interaction_stream_releases_the_connection_while_it_waits_for_the_worker(
    monkeypatch,
):
    from app.api.v1.responses import interaction_stream

    monkeypatch.setattr(interaction_stream, "CLAIM_POLL_INTERVAL_SECONDS", 0)
    service = _ClaimedThenBoundService()
    frames = [
        frame
        async for frame in interaction_stream.stream_claimed_interaction(service, "run_1")  # type: ignore[arg-type]
    ]

    assert frames == [": heartbeat\n\n", ": heartbeat\n\n"]
    # Two waits before the worker bound a response, one release each; the
    # tail that follows releases once more before it confirms the terminal.
    assert service.db.releases >= 2


class _FinishesBetweenReadsService(_FakeResponseService):
    """The worker commits RUN_FINISHED after the event list, before the status read."""

    async def get_response(self, response_id):
        self._events.append(
            SimpleNamespace(
                response_id="resp_test",
                sequence=2,
                source="ag-ui",
                type="RUN_FINISHED",
                payload_json={"type": "RUN_FINISHED", "threadId": "thread", "runId": "run"},
            )
        )
        return SimpleNamespace(status="succeeded")


@pytest.mark.asyncio
async def test_tail_drains_events_committed_between_the_list_and_the_terminal_read():
    items = []
    async for item in tail_response_events(
        _FinishesBetweenReadsService(), "resp_test", heartbeat_seconds=0, poll_interval_seconds=0
    ):
        items.append(item)

    assert [item["kind"] for item in items] == ["event", "event", "done"]
    assert items[1]["event"].type == "RUN_FINISHED"
