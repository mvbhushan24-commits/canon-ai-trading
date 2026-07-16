"""Unit tests for order block origin detection."""

from backend.engines.market_order_block.origin import OriginDetector
from backend.engines.market_order_block.schemas import OrderBlockDirection
from tests.unit.engines.order_block_conftest import (
    build_bearish_order_block_candles,
    build_bullish_order_block_candles,
)


def test_find_bullish_origins(order_block_config) -> None:
    detector = OriginDetector(order_block_config)
    candles = build_bullish_order_block_candles()
    origins = detector.find_bullish_origins(candles)

    assert len(origins) > 0
    assert all(origin.direction is OrderBlockDirection.BULLISH for origin in origins)


def test_find_bearish_origins(order_block_config) -> None:
    detector = OriginDetector(order_block_config)
    candles = build_bearish_order_block_candles()
    origins = detector.find_bearish_origins(candles)

    assert len(origins) > 0
    assert all(origin.direction is OrderBlockDirection.BEARISH for origin in origins)


def test_no_origins_with_insufficient_candles(order_block_config) -> None:
    detector = OriginDetector(order_block_config)
    candles = build_bullish_order_block_candles(count=3)
    assert detector.find_bullish_origins(candles) == []
