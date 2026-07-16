"""Unit tests for bullish fair value gap detection."""

from decimal import Decimal

from backend.engines.market_fvg.bullish import BullishFVGDetector
from backend.engines.market_fvg.engine import FairValueGapEngine
from backend.engines.market_fvg.schemas import FairValueGapDirection
from tests.unit.engines.fvg_conftest import build_bullish_fvg_candles, primary_bullish_formation


def test_bullish_detector_finds_three_candle_formation() -> None:
    candles = build_bullish_fvg_candles()
    formation = primary_bullish_formation(candles)

    assert formation.direction is FairValueGapDirection.BULLISH
    assert formation.candle_a_index == 12
    assert formation.candle_b_index == 13
    assert formation.candle_c_index == 14


def test_bullish_gap_boundaries() -> None:
    candles = build_bullish_fvg_candles()
    formation = primary_bullish_formation(candles)

    candle_a = candles[formation.candle_a_index]
    candle_c = candles[formation.candle_c_index]

    assert formation.low == Decimal(str(candle_a.high))
    assert formation.high == Decimal(str(candle_c.low))
    assert candle_a.high < candle_c.low


def test_bullish_gap_width() -> None:
    formation = primary_bullish_formation(build_bullish_fvg_candles())
    gap_size = formation.high - formation.low

    assert gap_size == Decimal("5")


def test_bullish_ce_calculation() -> None:
    candles = build_bullish_fvg_candles()
    engine = FairValueGapEngine()
    gaps = engine.detect_bullish_gaps(candles)

    gap = next(g for g in gaps if g.high == Decimal("2305") and g.low == Decimal("2300"))
    expected_ce = (gap.high + gap.low) / Decimal("2")
    assert gap.ce_price == expected_ce
    assert gap.ce_price == Decimal("2302.5")


def test_bullish_no_formation_when_no_gap() -> None:
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from tests.unit.engines.conftest import make_candle

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        make_candle(
            open_time=start + timedelta(hours=i),
            open_price=Decimal("2300"),
            high=Decimal("2302"),
            low=Decimal("2298"),
            close=Decimal("2301"),
        )
        for i in range(15)
    ]
    formations = BullishFVGDetector().find_formations(candles)
    assert not formations


def test_bullish_impulse_filter(fvg_config) -> None:
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from tests.unit.engines.conftest import make_candle

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []
    for index in range(12):
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=Decimal("2285"),
                high=Decimal("2290"),
                low=Decimal("2280"),
                close=Decimal("2288"),
            )
        )

    candles.append(
        make_candle(
            open_time=start + timedelta(hours=12),
            open_price=Decimal("2298"),
            high=Decimal("2300"),
            low=Decimal("2295"),
            close=Decimal("2299"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=13),
            open_price=Decimal("2301"),
            high=Decimal("2302"),
            low=Decimal("2300"),
            close=Decimal("2301.5"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=14),
            open_price=Decimal("2306"),
            high=Decimal("2318"),
            low=Decimal("2305"),
            close=Decimal("2315"),
        )
    )

    engine = FairValueGapEngine(config=fvg_config)
    gaps = engine.detect_bullish_gaps(candles)
    assert not any(g.high == Decimal("2305") and g.low == Decimal("2300") for g in gaps)
