"""Unit tests for mitigation block lifecycle classification."""

import pytest

pytest_plugins = ["tests.unit.engines.mitigation_conftest"]

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.engines.market_mitigation.engine import MitigationBlockEngine
from backend.engines.market_mitigation.lifecycle import LifecycleManager
from backend.engines.market_mitigation.schemas import (
    MitigationBlock,
    MitigationBlockDirection,
    MitigationBlockQuality,
    MitigationBlockStatus,
)
from tests.unit.engines.conftest import make_candle
from tests.unit.engines.mitigation_conftest import (
    build_bullish_mitigation_base_candles,
    build_bullish_mitigation_full_candles,
    build_bullish_mitigation_invalidation_candles,
    build_bullish_mitigation_touch_candles,
    build_mitigation_expiry_candles,
    mitigation_config,
)


def test_fresh_mitigation_block_status(mitigation_block_config) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    candles = build_bullish_mitigation_base_candles()
    analysis = engine.analyze(candles, timeframe="H1")

    assert analysis.fresh_blocks or analysis.mitigation_blocks
    assert any(
        block.status is MitigationBlockStatus.FRESH for block in analysis.mitigation_blocks
    )


def test_partial_on_wick_touch(mitigation_block_config) -> None:
    from tests.unit.engines.mitigation_conftest import build_bullish_mitigation_partial_candles

    lifecycle = LifecycleManager(mitigation_block_config)
    engine = MitigationBlockEngine(config=mitigation_block_config)
    candles = build_bullish_mitigation_partial_candles()
    blocks = engine.detect_bullish_blocks(candles[:20])
    assert blocks

    updated = lifecycle.update_status(blocks[0], candles)
    assert updated.status in {
        MitigationBlockStatus.PARTIAL,
        MitigationBlockStatus.CONFIRMED,
    }
    assert updated.touch_count >= 1
    assert updated.mitigation_percent > 0


def test_confirmed_on_wick_retest(mitigation_block_config) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    candles = build_bullish_mitigation_touch_candles()
    analysis = engine.analyze(candles, timeframe="H1")

    confirmed = [
        block
        for block in analysis.mitigation_blocks
        if block.is_confirmed or block.status is MitigationBlockStatus.CONFIRMED
    ]
    assert confirmed
    assert confirmed[0].confirmation_reason


def test_used_after_full_mitigation(mitigation_block_config) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    candles = build_bullish_mitigation_full_candles()
    analysis = engine.analyze(candles, timeframe="H1")

    used = [
        block for block in analysis.mitigation_blocks if block.status is MitigationBlockStatus.USED
    ]
    assert used
    assert used[0].used_bar_index is not None


def test_invalidated_on_close_break() -> None:
    lifecycle = LifecycleManager(mitigation_config(invalidation_mode="close"))
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        make_candle(
            open_time=start + timedelta(hours=index),
            open_price=Decimal("2320"),
            high=Decimal("2322"),
            low=Decimal("2318"),
            close=Decimal("2321"),
        )
        for index in range(17)
    ]
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=17),
            open_price=Decimal("2310"),
            high=Decimal("2312"),
            low=Decimal("2300"),
            close=Decimal("2302"),
        )
    )

    block = MitigationBlock(
        block_id="mb-inv-test",
        direction=MitigationBlockDirection.BULLISH,
        status=MitigationBlockStatus.CONFIRMED,
        high=Decimal("2315"),
        low=Decimal("2309"),
        origin_bar_index=14,
        origin_time_utc=candles[14].close_time_utc,
        displacement_bar_index=15,
        displacement_time_utc=candles[15].close_time_utc,
        formation_bar_index=16,
        formation_time_utc=candles[16].close_time_utc,
        touch_count=1,
        mitigation_percent=Decimal("50"),
        quality=MitigationBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        is_confirmed=True,
        confirmation_reason="Previously confirmed",
        confirmation_bar_index=16,
        confirmation_time_utc=candles[16].close_time_utc,
    )

    updated = lifecycle.update_status(block, candles)
    assert updated.status is MitigationBlockStatus.INVALIDATED
    assert updated.invalidation_bar_index is not None


def test_expired_without_retest() -> None:
    candles, config = build_mitigation_expiry_candles()
    engine = MitigationBlockEngine(config=config)
    analysis = engine.analyze(candles, timeframe="H1")

    expired = [
        block for block in analysis.mitigation_blocks if block.status is MitigationBlockStatus.EXPIRED
    ]
    assert expired
    assert expired[0].expiration_bar_index is not None


def test_track_touches_increments_count(mitigation_block_config) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    candles = build_bullish_mitigation_touch_candles()
    blocks = engine.detect_bullish_blocks(candles)

    assert blocks
    updated = engine.track_touches(blocks[0], candles)
    assert updated.touch_count >= blocks[0].touch_count


def test_validate_confirmation_method(mitigation_block_config) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    candles = build_bullish_mitigation_touch_candles()
    blocks = engine.detect_bullish_blocks(candles)

    assert blocks
    classified = engine.classify_lifecycle(blocks, candles)
    touched = next(
        (block for block in classified if block.status is MitigationBlockStatus.PARTIAL),
        classified[0],
    )
    assert engine.validate_confirmation(touched, candles) is True


def test_classify_lifecycle_preserves_block_id(mitigation_block_config) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    candles = build_bullish_mitigation_base_candles()
    blocks = engine.detect_bullish_blocks(candles)

    classified = engine.classify_lifecycle(blocks, candles)
    assert {block.block_id for block in blocks} == {block.block_id for block in classified}


def test_multi_touch_recorded(mitigation_block_config) -> None:
    from tests.unit.engines.conftest import make_candle
    from tests.unit.engines.mitigation_conftest import build_bullish_mitigation_partial_candles

    lifecycle = LifecycleManager(mitigation_block_config)
    candles = build_bullish_mitigation_partial_candles()
    start = candles[-1].open_time_utc + timedelta(hours=2)
    candles.append(
        make_candle(
            open_time=start,
            open_price=Decimal("2320"),
            high=Decimal("2322"),
            low=Decimal("2313"),
            close=Decimal("2318"),
        )
    )

    engine = MitigationBlockEngine(config=mitigation_block_config)
    blocks = engine.detect_bullish_blocks(candles)
    assert blocks

    first_touch = lifecycle.update_status(blocks[0], candles[:21])
    second_touch = lifecycle.update_status(first_touch, candles)
    assert second_touch.touch_count >= 2
