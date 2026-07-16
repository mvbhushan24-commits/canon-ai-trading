"""Unit tests for event publisher."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_data.events import EventPublisher
from backend.engines.market_data.schemas import GapInfo, NormalizedCandle, NormalizedTick


def test_event_publisher_tick_received(sample_symbol: str) -> None:
    publisher = EventPublisher()
    received: list[dict] = []
    publisher.subscribe("market.tick.received", lambda event: received.append(event.to_dict()))

    tick = NormalizedTick(
        symbol=sample_symbol,
        bid=Decimal("2350"),
        ask=Decimal("2350.5"),
        spread=Decimal("0.5"),
        timestamp_utc=datetime.now(tz=UTC),
    )
    publisher.publish_tick_received(tick)

    assert len(received) == 1
    assert received[0]["event_type"] == "market.tick.received"
    assert received[0]["source_engine"] == "market_data"
    assert received[0]["symbol"] == sample_symbol


def test_event_publisher_gap_detected(sample_symbol: str) -> None:
    publisher = EventPublisher()
    received: list[str] = []
    publisher.subscribe("market.data.gap_detected", lambda event: received.append(event.event_type))

    gap = GapInfo(
        symbol=sample_symbol,
        timeframe="H1",
        gap_start_utc=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
        gap_end_utc=datetime(2026, 1, 1, 2, 0, tzinfo=UTC),
        missing_bars=1,
    )
    publisher.publish_gap_detected(gap)

    assert received == ["market.data.gap_detected"]


def test_event_publisher_wildcard_handler(sample_symbol: str) -> None:
    publisher = EventPublisher()
    all_events: list[str] = []
    publisher.subscribe("*", lambda event: all_events.append(event.event_type))

    candle = NormalizedCandle(
        symbol=sample_symbol,
        timeframe="H1",
        open=Decimal("2300"),
        high=Decimal("2302"),
        low=Decimal("2299"),
        close=Decimal("2301"),
        volume=100,
        open_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        close_time_utc=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
        is_closed=True,
    )
    publisher.publish_candle_closed(candle)

    assert all_events == ["market.candle.closed"]
