"""Offline tests for backend/events/event_bus.py (async pub/sub)."""
import asyncio
import logging

import pytest

import gmrp_helpers as H

eb = H.load("gmrp_event_bus", "backend", "events", "event_bus.py")


def ev(t="PRICE_UP", ticker="X"):
    return eb.MarketEvent(type=t, ticker=ticker, market="us")


def test_market_event_defaults_are_independent_and_utc_iso():
    a, b = ev(), ev()
    a.data["k"] = 1
    assert b.data == {}
    assert a.timestamp.endswith("+00:00")


def test_publish_routes_to_specific_and_wildcard_in_that_order():
    bus = eb.EventBus()
    seen = []
    bus.subscribe("PRICE_UP", lambda e: seen.append(("specific", e.ticker)))
    bus.subscribe("*", lambda e: seen.append(("star", e.ticker)))
    bus.subscribe("PRICE_DOWN", lambda e: seen.append(("other", e.ticker)))
    asyncio.run(bus.publish(ev("PRICE_UP", "A")))
    assert seen == [("specific", "A"), ("star", "A")]


def test_publish_with_no_subscribers_only_records_history():
    bus = eb.EventBus()
    asyncio.run(bus.publish(ev()))
    assert len(bus.history) == 1


def test_history_is_bounded_and_returns_copy():
    bus = eb.EventBus(max_history=3)

    async def go():
        for i in range(5):
            await bus.publish(ev(ticker=str(i)))
    asyncio.run(go())
    assert [e.ticker for e in bus.history] == ["2", "3", "4"]
    bus.history.clear()
    assert len(bus.history) == 3


def test_default_history_cap_is_200():
    bus = eb.EventBus()

    async def go():
        for i in range(201):
            await bus.publish(ev(ticker=str(i)))
    asyncio.run(go())
    assert len(bus.history) == 200 and bus.history[0].ticker == "1"


def test_failing_callback_is_isolated_and_logged(caplog):
    bus = eb.EventBus()
    seen = []

    def boom(e):
        raise RuntimeError("x")
    bus.subscribe("PRICE_UP", boom)
    bus.subscribe("PRICE_UP", lambda e: seen.append(e.ticker))
    with caplog.at_level(logging.ERROR, logger=eb.log.name):
        asyncio.run(bus.publish(ev(ticker="Z")))
    assert seen == ["Z"]
    assert any("callback error" in r.getMessage() for r in caplog.records)


def test_coroutine_callbacks_are_scheduled():
    bus = eb.EventBus()
    seen = []

    async def cb(e):
        seen.append(e.ticker)

    async def go():
        bus.subscribe("*", cb)
        await bus.publish(ev(ticker="C"))
        assert seen == []          # scheduled, not yet run
        await asyncio.sleep(0)
    asyncio.run(go())
    assert seen == ["C"]


def test_unsubscribe_removes_only_that_callback_and_tolerates_unknown():
    bus = eb.EventBus()
    seen = []

    def a(e):
        seen.append("a")

    def b(e):
        seen.append("b")
    bus.subscribe("PRICE_UP", a)
    bus.subscribe("PRICE_UP", b)
    bus.unsubscribe("PRICE_UP", a)
    bus.unsubscribe("PRICE_UP", a)          # already gone: no error
    bus.unsubscribe("NEVER_SEEN", a)        # unknown type: no error
    asyncio.run(bus.publish(ev()))
    assert seen == ["b"]


def test_callback_subscribed_to_both_type_and_star_fires_twice():
    bus = eb.EventBus()
    seen = []

    def cb(e):
        seen.append(1)
    bus.subscribe("PRICE_UP", cb)
    bus.subscribe("*", cb)
    asyncio.run(bus.publish(ev()))
    assert len(seen) == 2


def test_module_singleton():
    assert isinstance(eb.bus, eb.EventBus)
