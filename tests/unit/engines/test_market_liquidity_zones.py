"""Unit tests for liquidity zone builder."""

from decimal import Decimal

from backend.engines.market_liquidity.equal import EqualLiquidityDetector
from backend.engines.market_liquidity.schemas import LiquiditySide
from backend.engines.market_liquidity.zones import ZoneBuilder
from tests.unit.engines.liquidity_conftest import build_equal_high_swings, build_equal_low_swings


def test_build_zones(liquidity_config) -> None:
    equal = EqualLiquidityDetector(liquidity_config)
    highs = equal.detect_equal_highs(None, build_equal_high_swings())
    lows = equal.detect_equal_lows(None, build_equal_low_swings())
    zones = ZoneBuilder(liquidity_config).build_zones(highs, lows)

    assert len(zones) == 2
    sides = {zone.side for zone in zones}
    assert LiquiditySide.BUY_SIDE in sides
    assert LiquiditySide.SELL_SIDE in sides
    for zone in zones:
        assert zone.upper_bound > zone.lower_bound
        assert zone.anchor_price > Decimal("0")
