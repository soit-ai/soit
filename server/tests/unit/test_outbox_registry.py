"""Unit tests for OutboxHandlerRegistry."""

from __future__ import annotations

from app.kernel.events.registry import OutboxHandlerRegistry


def _h(name: str):
    def _fn() -> str:
        return name

    return _fn


def test_get_handlers_empty_for_unknown_type() -> None:
    reg = OutboxHandlerRegistry()
    assert reg.get_handlers("missing.type") == []


def test_registration_order_preserved() -> None:
    reg = OutboxHandlerRegistry()
    reg.register("run.created", "c_first", _h("a"))
    reg.register("run.created", "c_second", _h("b"))
    reg.register("run.created", "c_third", _h("c"))
    handlers = reg.get_handlers("run.created")
    assert [h.consumer_name for h in handlers] == ["c_first", "c_second", "c_third"]
    assert [h.handler() for h in handlers] == ["a", "b", "c"]


def test_distinct_event_types_isolated() -> None:
    reg = OutboxHandlerRegistry()
    reg.register("a.e", "c1", _h("1"))
    reg.register("b.e", "c2", _h("2"))
    assert len(reg.get_handlers("a.e")) == 1
    assert len(reg.get_handlers("b.e")) == 1
    assert "a.e" in reg.event_types()
    assert "b.e" in reg.event_types()
