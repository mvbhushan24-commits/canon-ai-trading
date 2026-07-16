"""Unit tests for breaker block quality scoring."""

import pytest

pytest_plugins = ["tests.unit.engines.order_breaker_conftest"]

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_breaker.engine import BreakerBlockEngine
from backend.engines.market_breaker.quality import QualityScorer
from backend.engines.market_breaker.schemas import (
    BreakerBlockDirection,
    BreakerBlockQuality,
    BreakerBlockStatus,
    BreakerSourceType,
)
from backend.engines.market_fvg.schemas import (
    FairValueGap,
    FairValueGapDirection,
    FairValueGapQuality,
    FairValueGapState,
    FairValueGapStatus,
    PremiumDiscountZone,
)
from backend.engines.market_liquidity.schemas import LiquiditySide, LiquidityState, LiquidityZone
from tests.unit.engines.liquidity_conftest import build_sample_structure
from tests.unit.engines.order_breaker_conftest import (
    breaker_config,
    build_bearish_breaker_source_candles,
    build_breaker_base_candles,
    invalidated_bearish_order_block,
    invalidated_bullish_order_block,
)


def _sample_breaker():
    from backend.engines.market_breaker.schemas import BreakerBlock

    return BreakerBlock(
        breaker_id="brk-test",
        direction=BreakerBlockDirection.BEARISH,
        status=BreakerBlockStatus.CANDIDATE,
        high=Decimal("2316"),
        low=Decimal("2308"),
        source_type=BreakerSourceType.ORDER_BLOCK,
        source_id="ob-1",
        source_direction="bullish",
        invalidation_bar_index=17,
        invalidation_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        formation_bar_index=18,
        formation_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        quality=BreakerBlockQuality.LOW,
        strength=Decimal("0"),
        is_confirmed=False,
        confirmation_reason="Awaiting retest",
        structure_alignment=False,
        liquidity_confluence=False,
        fvg_confluence=False,
        evidence=["Source quality: high"],
    )


def test_passes_minimum(breaker_block_config) -> None:
    scorer = QualityScorer(breaker_block_config)
    engine = BreakerBlockEngine(config=breaker_block_config)
    candles = build_breaker_base_candles()
    block = invalidated_bullish_order_block(candles)
    breakers = engine.detect_bearish_breakers(candles, [block])

    assert breakers
    assert scorer.passes_minimum(breakers[0].strength)


def test_structure_alignment_scoring(breaker_block_config) -> None:
    engine = BreakerBlockEngine(config=breaker_block_config)
    candles = build_bearish_breaker_source_candles()
    block = invalidated_bearish_order_block(candles)
    structure = build_sample_structure()

    with_structure = engine.detect_bullish_breakers(candles, [block], structure)
    without_structure = engine.detect_bullish_breakers(candles, [block])

    assert with_structure
    assert without_structure
    assert with_structure[0].structure_alignment is True
    assert without_structure[0].structure_alignment is False


def test_quality_tier_classification(breaker_block_config) -> None:
    engine = BreakerBlockEngine(config=breaker_block_config)
    candles = build_breaker_base_candles()
    block = invalidated_bullish_order_block(candles)
    breakers = engine.detect_bearish_breakers(candles, [block], build_sample_structure())

    assert breakers
    assert breakers[0].quality in {
        BreakerBlockQuality.HIGH,
        BreakerBlockQuality.MEDIUM,
        BreakerBlockQuality.LOW,
    }
    assert breakers[0].strength >= Decimal(str(breaker_block_config.min_quality_score))


def test_liquidity_confluence_scoring(breaker_block_config) -> None:
    scorer = QualityScorer(breaker_block_config)
    breaker = _sample_breaker()
    liquidity_state = LiquidityState(
        active_zones=[
            LiquidityZone(
                zone_id="liq-1",
                upper_bound=Decimal("2320"),
                lower_bound=Decimal("2305"),
                side=LiquiditySide.BUY_SIDE,
                anchor_price=Decimal("2312"),
                cluster_size=3,
                timestamp_utc=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        ],
    )

    _, liquidity_confluence, ids = scorer._liquidity_score(breaker, liquidity_state, [])

    assert liquidity_confluence is True
    assert ids


def test_fvg_confluence_scoring(breaker_block_config) -> None:
    scorer = QualityScorer(breaker_block_config)
    breaker = _sample_breaker()
    fvg_state = FairValueGapState(
        active_gaps=[
            FairValueGap(
                gap_id="fvg-1",
                direction=FairValueGapDirection.BEARISH,
                status=FairValueGapStatus.OPEN,
                high=Decimal("2318"),
                low=Decimal("2306"),
                ce_price=Decimal("2312"),
                gap_size=Decimal("12"),
                gap_size_pips=Decimal("120"),
                origin_bar_index=12,
                origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
                candle_a_index=12,
                candle_b_index=13,
                candle_c_index=14,
                quality=FairValueGapQuality.HIGH,
                strength=Decimal("0.8"),
            ),
        ],
    )

    _, fvg_confluence, ids = scorer._fvg_score(breaker, fvg_state, [])

    assert fvg_confluence is True
    assert ids


def test_premium_discount_classification(breaker_block_config) -> None:
    scorer = QualityScorer(breaker_block_config)
    breaker = _sample_breaker()
    structure = build_sample_structure()

    zone, range_high, range_low, evidence = scorer.classify_premium_discount(breaker, structure)

    assert zone in PremiumDiscountZone
    assert range_high is not None
    assert range_low is not None
    assert evidence


def test_score_confluence_enrichment(breaker_block_config) -> None:
    engine = BreakerBlockEngine(config=breaker_block_config)
    breaker = _sample_breaker()
    fvg_state = FairValueGapState(
        active_gaps=[
            FairValueGap(
                gap_id="fvg-1",
                direction=FairValueGapDirection.BEARISH,
                status=FairValueGapStatus.OPEN,
                high=Decimal("2318"),
                low=Decimal("2306"),
                ce_price=Decimal("2312"),
                gap_size=Decimal("12"),
                gap_size_pips=Decimal("120"),
                origin_bar_index=12,
                origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
                candle_a_index=12,
                candle_b_index=13,
                candle_c_index=14,
                quality=FairValueGapQuality.HIGH,
                strength=Decimal("0.8"),
            ),
        ],
    )

    enriched = engine.score_confluence(breaker, None, fvg_state)

    assert enriched.fvg_confluence is True
    assert enriched.fvg_confluence_ids


def test_invalidation_displacement(breaker_block_config) -> None:
    scorer = QualityScorer(breaker_block_config)
    candles = build_breaker_base_candles()
    block = invalidated_bullish_order_block(candles)
    engine = BreakerBlockEngine(config=breaker_block_config)
    breakers = engine.detect_bearish_breakers(candles, [block])

    assert breakers
    displacement = scorer.compute_invalidation_displacement(breakers[0], candles)
    assert displacement >= Decimal("0")
