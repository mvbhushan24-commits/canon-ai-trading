"""Shared helpers for liquidity engine tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_structure.schemas import (
    MarketStructure,
    StructureState,
    SwingKind,
    SwingLabel,
    SwingPoint,
    TrendDirection,
)


def build_equal_high_swings() -> list[SwingPoint]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        SwingPoint(
            price=Decimal("2350.0"),
            timestamp_utc=start,
            bar_index=5,
            kind=SwingKind.SWING_HIGH,
            label=SwingLabel.LH,
        ),
        SwingPoint(
            price=Decimal("2350.2"),
            timestamp_utc=start + timedelta(hours=4),
            bar_index=10,
            kind=SwingKind.SWING_HIGH,
            label=SwingLabel.LH,
        ),
    ]


def build_equal_low_swings() -> list[SwingPoint]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        SwingPoint(
            price=Decimal("2300.0"),
            timestamp_utc=start + timedelta(hours=2),
            bar_index=7,
            kind=SwingKind.SWING_LOW,
            label=SwingLabel.HL,
        ),
        SwingPoint(
            price=Decimal("2300.1"),
            timestamp_utc=start + timedelta(hours=6),
            bar_index=12,
            kind=SwingKind.SWING_LOW,
            label=SwingLabel.LL,
        ),
    ]


def build_sweep_candles(level: Decimal) -> list[NormalizedCandle]:
    from tests.unit.engines.conftest import make_candle

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        make_candle(
            open_time=start + timedelta(hours=i),
            open_price=Decimal("2340"),
            high=Decimal("2345"),
            low=Decimal("2335"),
            close=Decimal("2342"),
        )
        for i in range(6)
    ]
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=6),
            open_price=level + Decimal("4"),
            high=level + Decimal("5"),
            low=level - Decimal("1"),
            close=level - Decimal("3"),
        )
    )
    return candles


def build_sample_structure() -> MarketStructure:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    highs = build_equal_high_swings()
    lows = build_equal_low_swings()
    state = StructureState(
        trend=TrendDirection.BULLISH,
        last_swing_high=highs[-1],
        last_swing_low=lows[-1],
        bar_count=30,
    )
    return MarketStructure(
        symbol="XAUUSD",
        timeframe="H1",
        timestamp_utc=start + timedelta(hours=30),
        current_trend=TrendDirection.BULLISH,
        swing_highs=highs,
        swing_lows=lows,
        internal_structure=state,
        external_structure=state,
        current_structure_state=state,
    )
