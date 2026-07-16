"""Unit tests for bearish fair value gap detection."""

from decimal import Decimal

from backend.engines.market_fvg.bearish import BearishFVGDetector
from backend.engines.market_fvg.engine import FairValueGapEngine
from backend.engines.market_fvg.schemas import FairValueGapDirection
from tests.unit.engines.fvg_conftest import build_bearish_fvg_candles, primary_bearish_formation


def test_bearish_detector_finds_three_candle_formation() -> None:
    candles = build_bearish_fvg_candles()
    formation = primary_bearish_formation(candles)

    assert formation.direction is FairValueGapDirection.BEARISH
    assert formation.candle_a_index == 12
    assert formation.candle_b_index == 13
    assert formation.candle_c_index == 14


def test_bearish_gap_boundaries() -> None:
    candles = build_bearish_fvg_candles()
    formation = primary_bearish_formation(candles)

    candle_a = candles[formation.candle_a_index]
    candle_c = candles[formation.candle_c_index]

    assert formation.low == Decimal(str(candle_c.high))
    assert formation.high == Decimal(str(candle_a.low))
    assert candle_a.low > candle_c.high


def test_bearish_gap_width() -> None:
    formation = primary_bearish_formation(build_bearish_fvg_candles())
    gap_size = formation.high - formation.low

    assert gap_size == Decimal("5")


def test_bearish_ce_calculation() -> None:
    candles = build_bearish_fvg_candles()
    engine = FairValueGapEngine()
    gaps = engine.detect_bearish_gaps(candles)

    gap = next(g for g in gaps if g.high == Decimal("2350") and g.low == Decimal("2345"))
    expected_ce = (gap.high + gap.low) / Decimal("2")
    assert gap.ce_price == expected_ce
    assert gap.ce_price == Decimal("2347.5")


def test_bearish_no_formation_when_no_gap() -> None:
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
    formations = BearishFVGDetector().find_formations(candles)
    assert not formations
