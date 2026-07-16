"""Unit tests for liquidity sweep and grab detection."""

from decimal import Decimal

from backend.engines.market_liquidity.schemas import LiquidityKind, LiquidityLevel, SweepDirection
from backend.engines.market_liquidity.sweep import SweepDetector
from tests.unit.engines.liquidity_conftest import build_sweep_candles


def test_detect_sweep_beyond_high(liquidity_config) -> None:
    level = Decimal("2350")
    candles = build_sweep_candles(level)
    detector = SweepDetector(liquidity_config)
    liquidity = LiquidityLevel(
        kind=LiquidityKind.BUY_SIDE,
        price=level,
        timestamp_utc=candles[0].open_time_utc,
        bar_index=0,
    )

    sweeps = detector.detect_sweeps(candles, [liquidity], "H1")

    assert len(sweeps) >= 1
    assert sweeps[0].direction == SweepDirection.BEARISH
    assert sweeps[0].sweep_price > level
    assert sweeps[0].reclaim_price < level


def test_detect_grab_after_sweep(liquidity_config) -> None:
    level = Decimal("2350")
    candles = build_sweep_candles(level)
    detector = SweepDetector(liquidity_config)
    liquidity = LiquidityLevel(
        kind=LiquidityKind.BUY_SIDE,
        price=level,
        timestamp_utc=candles[0].open_time_utc,
        bar_index=0,
    )
    sweeps = detector.detect_sweeps(candles, [liquidity], "H1")
    grabs = detector.detect_grabs(candles, sweeps, "H1")

    assert len(grabs) >= 1
    assert grabs[0].rejection_ratio > Decimal("0")
