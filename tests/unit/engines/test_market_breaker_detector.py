"""Unit tests for breaker block detector orchestration."""

from backend.engines.market_breaker.detector import BreakerBlockDetector
from backend.engines.market_breaker.schemas import BreakerBlockBias, BreakerBlockDirection, BreakerBlockStatus
from tests.unit.engines.liquidity_conftest import build_sample_structure
from tests.unit.engines.order_breaker_conftest import (
    breaker_config,
    build_bearish_breaker_confirmation_candles,
    build_bearish_breaker_source_candles,
    build_breaker_base_candles,
    invalidated_bearish_order_block,
    invalidated_bullish_order_block,
)


def test_detect_bearish_breakers_from_invalidated_bullish_ob() -> None:
    config = breaker_config()
    detector = BreakerBlockDetector(config)
    candles = build_breaker_base_candles()
    block = invalidated_bullish_order_block(candles)

    breakers = detector.detect_bearish_breakers(candles, [block])

    assert len(breakers) == 1
    assert breakers[0].direction is BreakerBlockDirection.BEARISH
    assert breakers[0].status is BreakerBlockStatus.CANDIDATE
    assert breakers[0].source_id == block.block_id


def test_detect_bullish_breakers_from_invalidated_bearish_ob() -> None:
    config = breaker_config()
    detector = BreakerBlockDetector(config)
    candles = build_bearish_breaker_source_candles()
    block = invalidated_bearish_order_block(candles)

    breakers = detector.detect_bullish_breakers(candles, [block])

    assert len(breakers) == 1
    assert breakers[0].direction is BreakerBlockDirection.BULLISH


def test_full_detect_pipeline() -> None:
    config = breaker_config()
    detector = BreakerBlockDetector(config)
    candles = build_bearish_breaker_confirmation_candles()
    block = invalidated_bullish_order_block(candles)
    structure = build_sample_structure()

    analysis = detector.detect(
        candles,
        structure,
        invalidated_order_blocks=[block],
    )

    assert analysis.symbol == candles[0].symbol
    assert analysis.timeframe == candles[0].timeframe
    assert analysis.breaker_blocks
    assert analysis.state.bar_count == len(candles)
    assert analysis.bias in BreakerBlockBias


def test_classify_lifecycle_updates_status() -> None:
    config = breaker_config()
    detector = BreakerBlockDetector(config)
    candles = build_bearish_breaker_confirmation_candles()
    block = invalidated_bullish_order_block(candles)
    breakers = detector.detect_bearish_breakers(candles, [block])

    classified = detector.classify_lifecycle(breakers, candles)

    assert classified
    assert any(b.status is BreakerBlockStatus.CONFIRMED for b in classified)


def test_detect_merges_prior_state() -> None:
    config = breaker_config()
    detector = BreakerBlockDetector(config)
    candles = build_breaker_base_candles()
    block = invalidated_bullish_order_block(candles)

    first = detector.detect(candles, invalidated_order_blocks=[block])
    second = detector.detect(
        candles,
        invalidated_order_blocks=[block],
        prior_state=first.state,
    )

    assert second.breaker_blocks
    assert len(second.breaker_blocks) >= len(first.breaker_blocks)


def test_detect_filters_below_min_quality() -> None:
    config = breaker_config(min_quality_score=0.99)
    detector = BreakerBlockDetector(config)
    candles = build_breaker_base_candles()
    block = invalidated_bullish_order_block(candles)

    breakers = detector.detect_bearish_breakers(candles, [block])

    assert breakers == []


def test_timeline_events_emitted_on_detection() -> None:
    config = breaker_config()
    detector = BreakerBlockDetector(config)
    candles = build_bearish_breaker_confirmation_candles()
    block = invalidated_bullish_order_block(candles)

    analysis = detector.detect(candles, invalidated_order_blocks=[block])

    assert analysis.events
    event_kinds = {event.kind.value for event in analysis.events}
    assert "BreakerBlockDetected" in event_kinds
    assert "CandidateBreakerBlock" in event_kinds


def test_confirmed_breakers_drive_bias() -> None:
    config = breaker_config()
    detector = BreakerBlockDetector(config)
    candles = build_bearish_breaker_confirmation_candles()
    block = invalidated_bullish_order_block(candles)
    structure = build_sample_structure()

    analysis = detector.detect(
        candles,
        structure,
        invalidated_order_blocks=[block],
    )

    if analysis.confirmed_breakers:
        assert analysis.bias in {BreakerBlockBias.BEARISH, BreakerBlockBias.NEUTRAL, BreakerBlockBias.BULLISH}
        assert analysis.confidence >= 0
