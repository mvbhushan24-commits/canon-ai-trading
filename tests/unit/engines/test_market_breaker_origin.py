"""Unit tests for breaker block origin detection."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_breaker.origin import OriginDetector
from backend.engines.market_breaker.schemas import BreakerBlockDirection, BreakerSourceType
from backend.engines.market_fvg.schemas import (
    FairValueGap,
    FairValueGapDirection,
    FairValueGapQuality,
    FairValueGapStatus,
)
from backend.engines.market_order_block.schemas import OrderBlockQuality, OrderBlockStatus
from tests.unit.engines.order_breaker_conftest import (
    breaker_config,
    build_bearish_breaker_source_candles,
    build_breaker_base_candles,
    invalidated_bearish_order_block,
    invalidated_bullish_order_block,
)


def test_derive_bearish_breaker_from_invalidated_bullish_ob() -> None:
    config = breaker_config()
    detector = OriginDetector(config)
    candles = build_breaker_base_candles()
    block = invalidated_bullish_order_block(candles)

    candidates = detector.derive_from_order_blocks([block], candles)

    assert len(candidates) == 1
    assert candidates[0].direction is BreakerBlockDirection.BEARISH
    assert candidates[0].source_type is BreakerSourceType.ORDER_BLOCK
    assert candidates[0].source_id == block.block_id
    assert candidates[0].source_direction == "bullish"


def test_derive_bullish_breaker_from_invalidated_bearish_ob() -> None:
    config = breaker_config()
    detector = OriginDetector(config)
    candles = build_bearish_breaker_source_candles()
    block = invalidated_bearish_order_block(candles)

    candidates = detector.derive_from_order_blocks([block], candles)

    assert len(candidates) == 1
    assert candidates[0].direction is BreakerBlockDirection.BULLISH
    assert candidates[0].source_direction == "bearish"


def test_skips_non_invalidated_fvgs_when_enabled() -> None:
    config = breaker_config(fvg_breaker_enabled=True)
    detector = OriginDetector(config)
    candles = build_breaker_base_candles()
    open_gap = FairValueGap(
        gap_id="fvg-open",
        direction=FairValueGapDirection.BULLISH,
        status=FairValueGapStatus.OPEN,
        high=Decimal("2316"),
        low=Decimal("2308"),
        ce_price=Decimal("2312"),
        gap_size=Decimal("8"),
        gap_size_pips=Decimal("80"),
        origin_bar_index=14,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        candle_a_index=14,
        candle_b_index=15,
        candle_c_index=16,
        quality=FairValueGapQuality.HIGH,
        strength=Decimal("0.8"),
    )

    assert detector.derive_from_fvgs([open_gap], candles) == []


def test_derives_from_invalidated_fvg_when_enabled() -> None:
    config = breaker_config(fvg_breaker_enabled=True)
    detector = OriginDetector(config)
    candles = build_breaker_base_candles()
    gap = FairValueGap(
        gap_id="fvg-inv",
        direction=FairValueGapDirection.BULLISH,
        status=FairValueGapStatus.INVALIDATED,
        high=Decimal("2316"),
        low=Decimal("2308"),
        ce_price=Decimal("2312"),
        gap_size=Decimal("8"),
        gap_size_pips=Decimal("80"),
        origin_bar_index=14,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        candle_a_index=14,
        candle_b_index=15,
        candle_c_index=16,
        invalidation_bar_index=17,
        quality=FairValueGapQuality.HIGH,
        strength=Decimal("0.8"),
    )

    candidates = detector.derive_from_fvgs([gap], candles)

    assert len(candidates) == 1
    assert candidates[0].direction is BreakerBlockDirection.BEARISH
    assert candidates[0].source_type is BreakerSourceType.FAIR_VALUE_GAP


def test_skips_low_quality_sources() -> None:
    config = breaker_config(min_source_quality="high")
    detector = OriginDetector(config)
    candles = build_breaker_base_candles()
    block = invalidated_bullish_order_block(candles).model_copy(
        update={"quality": OrderBlockQuality.LOW},
    )

    assert detector.derive_from_order_blocks([block], candles) == []


def test_skips_tiny_zones() -> None:
    config = breaker_config(min_zone_size_pips=100.0)
    detector = OriginDetector(config)
    candles = build_breaker_base_candles()
    block = invalidated_bullish_order_block(candles)

    assert detector.derive_from_order_blocks([block], candles) == []


def test_deduplicates_by_source_id() -> None:
    config = breaker_config(deduplicate_by_source=True)
    detector = OriginDetector(config)
    candles = build_breaker_base_candles()
    block = invalidated_bullish_order_block(candles)

    candidates = detector.derive_from_order_blocks([block, block], candles)

    assert len(candidates) == 1


def test_fvg_breaker_disabled_by_default() -> None:
    config = breaker_config(fvg_breaker_enabled=False)
    detector = OriginDetector(config)
    candles = build_breaker_base_candles()
    gap = FairValueGap(
        gap_id="fvg-inv",
        direction=FairValueGapDirection.BEARISH,
        status=FairValueGapStatus.INVALIDATED,
        high=Decimal("2347"),
        low=Decimal("2339"),
        ce_price=Decimal("2343"),
        gap_size=Decimal("8"),
        gap_size_pips=Decimal("80"),
        origin_bar_index=10,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        candle_a_index=10,
        candle_b_index=11,
        candle_c_index=12,
        invalidation_bar_index=13,
        quality=FairValueGapQuality.HIGH,
        strength=Decimal("0.8"),
    )

    assert detector.derive_from_fvgs([gap], candles) == []
