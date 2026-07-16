"""Unit tests for trend, BOS, and CHoCH detection."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.engines.market_structure.bos import BOSDetector
from backend.engines.market_structure.choch import CHoCHDetector
from backend.engines.market_structure.schemas import (
    BOSDirection,
    CHoCHDirection,
    SwingKind,
    SwingLabel,
    SwingPoint,
    TrendDirection,
)
from backend.engines.market_structure.trend import TrendAnalyzer
from tests.unit.engines.conftest import make_candle


def test_trend_bullish() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    highs = [
        SwingPoint(
            price=Decimal("100"),
            timestamp_utc=start,
            bar_index=1,
            kind=SwingKind.SWING_HIGH,
            label=SwingLabel.NONE,
        ),
        SwingPoint(
            price=Decimal("110"),
            timestamp_utc=start + timedelta(hours=2),
            bar_index=5,
            kind=SwingKind.SWING_HIGH,
            label=SwingLabel.HH,
        ),
    ]
    lows = [
        SwingPoint(
            price=Decimal("90"),
            timestamp_utc=start + timedelta(hours=1),
            bar_index=3,
            kind=SwingKind.SWING_LOW,
            label=SwingLabel.NONE,
        ),
        SwingPoint(
            price=Decimal("95"),
            timestamp_utc=start + timedelta(hours=3),
            bar_index=7,
            kind=SwingKind.SWING_LOW,
            label=SwingLabel.HL,
        ),
    ]

    trend, evidence, confidence = TrendAnalyzer().determine_trend(highs, lows)

    assert trend == TrendDirection.BULLISH
    assert evidence
    assert confidence > 0


def test_bos_bullish_break() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        make_candle(
            open_time=start + timedelta(hours=i),
            open_price=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("99"),
            close=Decimal("104"),
        )
        for i in range(8)
    ]
    candles[-1] = make_candle(
        open_time=start + timedelta(hours=8),
        open_price=Decimal("104"),
        high=Decimal("112"),
        low=Decimal("103"),
        close=Decimal("111"),
    )

    highs = [
        SwingPoint(
            price=Decimal("105"),
            timestamp_utc=start + timedelta(hours=2),
            bar_index=2,
            kind=SwingKind.SWING_HIGH,
        ),
        SwingPoint(
            price=Decimal("108"),
            timestamp_utc=start + timedelta(hours=5),
            bar_index=5,
            kind=SwingKind.SWING_HIGH,
        ),
    ]
    lows: list[SwingPoint] = []

    events = BOSDetector().detect(candles, highs, lows, TrendDirection.BULLISH, "H1")

    assert len(events) >= 1
    assert events[0].direction == BOSDirection.BULLISH


def test_choch_bearish_in_bullish_trend() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        make_candle(
            open_time=start + timedelta(hours=i),
            open_price=Decimal("110"),
            high=Decimal("111"),
            low=Decimal("109"),
            close=Decimal("110"),
        )
        for i in range(6)
    ]
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=6),
            open_price=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("88"),
            close=Decimal("89"),
        )
    )

    highs: list[SwingPoint] = []
    lows = [
        SwingPoint(
            price=Decimal("95"),
            timestamp_utc=start + timedelta(hours=3),
            bar_index=3,
            kind=SwingKind.SWING_LOW,
        ),
    ]

    events = CHoCHDetector().detect(candles, highs, lows, TrendDirection.BULLISH, "H1")

    assert len(events) == 1
    assert events[0].direction == CHoCHDirection.BEARISH
