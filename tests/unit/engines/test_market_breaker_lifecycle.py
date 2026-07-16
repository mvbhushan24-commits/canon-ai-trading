"""Unit tests for breaker block lifecycle classification."""

import pytest

pytest_plugins = ["tests.unit.engines.order_breaker_conftest"]

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.engines.market_breaker.engine import BreakerBlockEngine
from backend.engines.market_breaker.lifecycle import LifecycleManager
from backend.engines.market_breaker.schemas import BreakerBlockStatus
from tests.unit.engines.conftest import make_candle
from tests.unit.engines.order_breaker_conftest import (
    breaker_config,
    build_bearish_breaker_confirmation_candles,
    build_bearish_breaker_source_candles,
    build_breaker_base_candles,
    build_breaker_expiry_candles,
    build_breaker_mitigation_candles,
    build_bullish_breaker_confirmation_candles,
    invalidated_bearish_order_block,
    invalidated_bullish_order_block,
)


def test_candidate_breaker_status(breaker_block_config) -> None:
    engine = BreakerBlockEngine(config=breaker_block_config)
    candles = build_breaker_base_candles()
    block = invalidated_bullish_order_block(candles)
    analysis = engine.analyze(candles, invalidated_order_blocks=[block], timeframe="H1")

    assert analysis.candidate_breakers or analysis.breaker_blocks
    assert any(
        breaker.status is BreakerBlockStatus.CANDIDATE for breaker in analysis.breaker_blocks
    )


def test_confirmed_on_wick_retest(breaker_block_config) -> None:
    engine = BreakerBlockEngine(config=breaker_block_config)
    candles = build_bearish_breaker_confirmation_candles()
    block = invalidated_bullish_order_block(candles)
    analysis = engine.analyze(candles, invalidated_order_blocks=[block], timeframe="H1")

    confirmed = [
        breaker for breaker in analysis.breaker_blocks if breaker.status is BreakerBlockStatus.CONFIRMED
    ]
    assert confirmed
    assert confirmed[0].confirmation_bar_index is not None
    assert confirmed[0].is_confirmed is True


def test_mitigated_after_confirmation(breaker_block_config) -> None:
    engine = BreakerBlockEngine(config=breaker_block_config)
    candles = build_breaker_mitigation_candles()
    block = invalidated_bullish_order_block(candles)
    analysis = engine.analyze(candles, invalidated_order_blocks=[block], timeframe="H1")

    mitigated = [
        breaker for breaker in analysis.breaker_blocks if breaker.status is BreakerBlockStatus.MITIGATED
    ]
    assert mitigated
    assert mitigated[0].mitigation_bar_index is not None


def test_invalidated_on_close_break(breaker_block_config) -> None:
    from datetime import UTC, datetime

    from backend.engines.market_breaker.schemas import (
        BreakerBlock,
        BreakerBlockDirection,
        BreakerBlockQuality,
        BreakerSourceType,
    )

    lifecycle = LifecycleManager(breaker_block_config)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        make_candle(open_time=start + timedelta(hours=index), open_price=Decimal("2340"), high=Decimal("2342"), low=Decimal("2338"), close=Decimal("2341"))
        for index in range(15)
    ]
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=15),
            open_price=Decimal("2341"),
            high=Decimal("2344"),
            low=Decimal("2339"),
            close=Decimal("2343"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=16),
            open_price=Decimal("2338"),
            high=Decimal("2339"),
            low=Decimal("2330"),
            close=Decimal("2331"),
        )
    )

    breaker = BreakerBlock(
        breaker_id="brk-inv-test",
        direction=BreakerBlockDirection.BULLISH,
        status=BreakerBlockStatus.CONFIRMED,
        high=Decimal("2347"),
        low=Decimal("2339"),
        source_type=BreakerSourceType.ORDER_BLOCK,
        source_id="ob-test",
        source_direction="bearish",
        invalidation_bar_index=13,
        invalidation_time_utc=candles[13].close_time_utc,
        formation_bar_index=16,
        formation_time_utc=candles[16].close_time_utc,
        confirmation_bar_index=15,
        confirmation_time_utc=candles[15].close_time_utc,
        quality=BreakerBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        is_confirmed=True,
        confirmation_reason="Test confirmation",
        structure_alignment=False,
        liquidity_confluence=False,
        fvg_confluence=False,
    )

    updated = lifecycle.update_status(breaker, candles)

    assert updated.status is BreakerBlockStatus.INVALIDATED
    assert updated.invalidation_breaker_bar_index == 16


def test_expired_without_retest(breaker_block_config) -> None:
    candles, config = build_breaker_expiry_candles()
    engine = BreakerBlockEngine(config=config)
    block = invalidated_bullish_order_block(candles)
    analysis = engine.analyze(candles, invalidated_order_blocks=[block], timeframe="H1")

    expired = [
        breaker for breaker in analysis.breaker_blocks if breaker.status is BreakerBlockStatus.EXPIRED
    ]
    assert expired
    assert expired[0].expiration_bar_index is not None


def test_validate_confirmation_method(breaker_block_config) -> None:
    lifecycle = LifecycleManager(breaker_block_config)
    engine = BreakerBlockEngine(config=breaker_block_config)
    candles = build_bearish_breaker_confirmation_candles()
    block = invalidated_bullish_order_block(candles)
    breakers = engine.detect_bearish_breakers(candles, [block])

    assert breakers
    assert lifecycle.validate_confirmation(breakers[0], candles) is True


def test_compute_confirmation_reason(breaker_block_config) -> None:
    lifecycle = LifecycleManager(breaker_block_config)
    engine = BreakerBlockEngine(config=breaker_block_config)
    candles = build_breaker_base_candles()
    block = invalidated_bullish_order_block(candles)
    breakers = engine.detect_bearish_breakers(candles, [block])

    assert breakers
    reason = lifecycle.compute_confirmation_reason(breakers[0], candles)
    assert "Awaiting retest" in reason or "Wick entered" in reason


def test_lifecycle_manager_update_status(breaker_block_config) -> None:
    lifecycle = LifecycleManager(breaker_block_config)
    engine = BreakerBlockEngine(config=breaker_block_config)
    candles = build_bearish_breaker_confirmation_candles()
    block = invalidated_bullish_order_block(candles)
    breakers = engine.detect_bearish_breakers(candles, [block])

    assert breakers
    updated = lifecycle.update_status(breakers[0], candles)
    assert updated.status is BreakerBlockStatus.CONFIRMED


def test_rejection_confirmation_mode() -> None:
    config = breaker_config(confirmation_mode="rejection", rejection_wick_ratio=0.4)
    lifecycle = LifecycleManager(config)
    engine = BreakerBlockEngine(config=config)
    candles = build_bearish_breaker_source_candles(20)
    block = invalidated_bullish_order_block(candles)
    breakers = engine.detect_bearish_breakers(candles, [block])
    assert breakers

    start = candles[-1].open_time_utc + timedelta(hours=1)
    rejection_candle = make_candle(
        open_time=start,
        open_price=Decimal("2320"),
        high=Decimal("2314"),
        low=Decimal("2304"),
        close=Decimal("2310"),
    )
    extended = candles + [rejection_candle]
    updated = lifecycle.update_status(breakers[0], extended)
    assert updated.status in {BreakerBlockStatus.CONFIRMED, BreakerBlockStatus.CANDIDATE}


def test_body_touch_confirmation_mode() -> None:
    config = breaker_config(confirmation_mode="body_touch")
    lifecycle = LifecycleManager(config)
    engine = BreakerBlockEngine(config=config)
    candles = build_bearish_breaker_source_candles(20)
    block = invalidated_bullish_order_block(candles)
    breakers = engine.detect_bearish_breakers(candles, [block])
    assert breakers

    start = candles[-1].open_time_utc + timedelta(hours=1)
    body_touch = make_candle(
        open_time=start,
        open_price=Decimal("2320"),
        high=Decimal("2312"),
        low=Decimal("2309"),
        close=Decimal("2311"),
    )
    extended = candles + [body_touch]
    updated = lifecycle.update_status(breakers[0], extended)
    assert updated.status is BreakerBlockStatus.CONFIRMED
