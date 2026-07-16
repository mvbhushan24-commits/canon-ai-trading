"""Unit tests for order block lifecycle classification."""

from backend.engines.market_order_block.engine import OrderBlockEngine
from backend.engines.market_order_block.lifecycle import LifecycleManager
from backend.engines.market_order_block.schemas import OrderBlockStatus
from tests.unit.engines.order_block_conftest import (
    build_bullish_order_block_candles,
    build_mitigation_candles,
)


def test_fresh_block_status(order_block_config) -> None:
    engine = OrderBlockEngine(config=order_block_config)
    candles = build_bullish_order_block_candles()
    blocks = engine.detect_bullish_blocks(candles)
    classified = engine.classify_lifecycle(blocks, candles)

    assert classified
    assert any(block.status is OrderBlockStatus.FRESH for block in classified)


def test_mitigated_on_zone_touch(order_block_config) -> None:
    engine = OrderBlockEngine(config=order_block_config)
    candles = build_mitigation_candles()
    analysis = engine.analyze(candles, timeframe="H1")

    assert any(block.status is OrderBlockStatus.MITIGATED for block in analysis.order_blocks)
    mitigated = [block for block in analysis.order_blocks if block.status is OrderBlockStatus.MITIGATED]
    assert mitigated[0].mitigation_bar_index is not None


def test_invalidated_on_close_break(order_block_config) -> None:
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from tests.unit.engines.conftest import make_candle

    lifecycle = LifecycleManager(order_block_config)
    engine = OrderBlockEngine(config=order_block_config)
    candles = build_bullish_order_block_candles()
    blocks = engine.detect_bullish_blocks(candles)
    assert blocks

    block = blocks[0]
    start = candles[-1].open_time_utc + timedelta(hours=1)
    invalidate_candle = make_candle(
        open_time=start,
        open_price=block.low - Decimal("5"),
        high=block.low - Decimal("1"),
        low=block.low - Decimal("10"),
        close=block.low - Decimal("8"),
    )
    extended = candles + [invalidate_candle]
    updated = lifecycle.update_status(block, extended)

    assert updated.status is OrderBlockStatus.INVALIDATED
    assert updated.invalidation_bar_index is not None


def test_expire_old_blocks(order_block_config) -> None:
    lifecycle = LifecycleManager(order_block_config)
    engine = OrderBlockEngine(config=order_block_config)
    candles = build_bullish_order_block_candles()
    blocks = engine.detect_bullish_blocks(candles)
    assert blocks

    expired = lifecycle.expire_old_blocks(
        blocks,
        current_bar_count=blocks[0].origin_bar_index + order_block_config.max_block_age_bars + 1,
    )
    assert all(block.status is OrderBlockStatus.INVALIDATED for block in expired)
