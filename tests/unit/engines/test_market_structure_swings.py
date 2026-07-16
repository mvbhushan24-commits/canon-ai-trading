"""Unit tests for swing detection."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.engines.market_structure.schemas import SwingKind, SwingLabel
from backend.engines.market_structure.swings import SwingDetector
from tests.unit.engines.conftest import make_candle


def test_detect_swing_high_and_low() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    prices = [10, 12, 15, 13, 11, 10, 12, 16, 14, 11]
    candles = []
    for index, close in enumerate(prices):
        high = Decimal(str(close + 1))
        low = Decimal(str(close - 1))
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=Decimal(str(close)),
                high=high,
                low=low,
                close=Decimal(str(close)),
            )
        )

    detector = SwingDetector()
    highs, lows = detector.detect(candles, lookback=2)

    assert any(s.kind == SwingKind.SWING_HIGH for s in highs)
    assert any(s.kind == SwingKind.SWING_LOW for s in lows)


def test_label_swings_hh_hl() -> None:
    detector = SwingDetector()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    from backend.engines.market_structure.schemas import SwingPoint

    highs = [
        SwingPoint(
            price=Decimal("100"),
            timestamp_utc=start,
            bar_index=1,
            kind=SwingKind.SWING_HIGH,
        ),
        SwingPoint(
            price=Decimal("110"),
            timestamp_utc=start + timedelta(hours=2),
            bar_index=5,
            kind=SwingKind.SWING_HIGH,
        ),
    ]
    lows = [
        SwingPoint(
            price=Decimal("90"),
            timestamp_utc=start + timedelta(hours=1),
            bar_index=3,
            kind=SwingKind.SWING_LOW,
        ),
        SwingPoint(
            price=Decimal("95"),
            timestamp_utc=start + timedelta(hours=3),
            bar_index=7,
            kind=SwingKind.SWING_LOW,
        ),
    ]

    labeled_highs, labeled_lows, hh, hl, lh, ll = detector.label_swings(highs, lows)

    assert labeled_highs[1].label == SwingLabel.HH
    assert labeled_lows[1].label == SwingLabel.HL
    assert len(hh) == 1
    assert len(hl) == 1
    assert len(lh) == 0
    assert len(ll) == 0


def test_deduplicate_swings() -> None:
    from backend.engines.market_structure.schemas import SwingPoint

    start = datetime(2026, 1, 1, tzinfo=UTC)
    swings = [
        SwingPoint(
            price=Decimal("1"),
            timestamp_utc=start,
            bar_index=1,
            kind=SwingKind.SWING_HIGH,
        ),
        SwingPoint(
            price=Decimal("1"),
            timestamp_utc=start,
            bar_index=1,
            kind=SwingKind.SWING_HIGH,
        ),
    ]
    result = SwingDetector().deduplicate_swings(swings)
    assert len(result) == 1
