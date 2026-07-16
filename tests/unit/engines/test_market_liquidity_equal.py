"""Unit tests for equal high/low and buy/sell-side liquidity detection."""

from decimal import Decimal

from backend.engines.market_liquidity.equal import EqualLiquidityDetector
from backend.engines.market_liquidity.schemas import LiquidityKind
from tests.unit.engines.liquidity_conftest import build_equal_high_swings, build_equal_low_swings


def test_detect_equal_highs(liquidity_config) -> None:
    detector = EqualLiquidityDetector(liquidity_config)
    clusters = detector.detect_equal_highs(None, build_equal_high_swings())

    assert len(clusters) == 1
    assert clusters[0].kind == LiquidityKind.EQUAL_HIGH
    assert clusters[0].touched_count == 2


def test_detect_equal_lows(liquidity_config) -> None:
    detector = EqualLiquidityDetector(liquidity_config)
    clusters = detector.detect_equal_lows(None, build_equal_low_swings())

    assert len(clusters) == 1
    assert clusters[0].kind == LiquidityKind.EQUAL_LOW
    assert clusters[0].touched_count == 2


def test_detect_buy_side(liquidity_config) -> None:
    detector = EqualLiquidityDetector(liquidity_config)
    equal_highs = detector.detect_equal_highs(None, build_equal_high_swings())
    buy_side = detector.detect_buy_side(equal_highs)

    assert len(buy_side) == 1
    assert buy_side[0].kind == LiquidityKind.BUY_SIDE
    assert buy_side[0].price > Decimal("2349")


def test_detect_sell_side(liquidity_config) -> None:
    detector = EqualLiquidityDetector(liquidity_config)
    equal_lows = detector.detect_equal_lows(None, build_equal_low_swings())
    sell_side = detector.detect_sell_side(equal_lows)

    assert len(sell_side) == 1
    assert sell_side[0].kind == LiquidityKind.SELL_SIDE
    assert sell_side[0].price < Decimal("2301")
