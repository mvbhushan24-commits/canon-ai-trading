"""Unit tests for market data normalizer."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_data.normalizer import MarketDataNormalizer
from backend.engines.market_data.timeframes import timeframe_duration
from tests.conftest import MockRate, MockTick


def test_normalize_tick(sample_symbol: str) -> None:
    normalizer = MarketDataNormalizer()
    tick = normalizer.normalize_tick(
        sample_symbol,
        MockTick(bid=2350.10, ask=2350.60, time=int(datetime(2026, 1, 1, tzinfo=UTC).timestamp())),
    )

    assert tick.symbol == sample_symbol
    assert tick.bid == Decimal("2350.1")
    assert tick.ask == Decimal("2350.6")
    assert tick.spread == Decimal("0.5")
    assert tick.source == "mt5_xmglobal"
    assert tick.timestamp_utc.tzinfo == UTC


def test_normalize_candle(sample_symbol: str) -> None:
    normalizer = MarketDataNormalizer()
    open_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    candle = normalizer.normalize_candle(
        sample_symbol,
        "H1",
        MockRate(
            time=int(open_time.timestamp()),
            open=2300.0,
            high=2305.0,
            low=2298.0,
            close=2302.0,
            tick_volume=150,
        ),
        is_closed=True,
    )

    assert candle.symbol == sample_symbol
    assert candle.timeframe == "H1"
    assert candle.open == Decimal("2300.0")
    assert candle.high == Decimal("2305.0")
    assert candle.low == Decimal("2298.0")
    assert candle.close == Decimal("2302.0")
    assert candle.volume == 150
    assert candle.is_closed is True
    assert candle.close_time_utc == open_time + timeframe_duration("H1")
