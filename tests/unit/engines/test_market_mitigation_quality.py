"""Unit tests for mitigation block quality scoring."""

import pytest

pytest_plugins = ["tests.unit.engines.mitigation_conftest"]

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_mitigation.engine import MitigationBlockEngine
from backend.engines.market_mitigation.quality import QualityScorer
from backend.engines.market_mitigation.schemas import (
    MitigationBlock,
    MitigationBlockDirection,
    MitigationBlockQuality,
    MitigationBlockStatus,
    StructureScope,
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
from tests.unit.engines.mitigation_conftest import (
    build_bearish_mitigation_base_candles,
    build_bullish_mitigation_base_candles,
    mitigation_config,
    parent_order_block_for_bullish_mitigation,
    sample_htf_mitigation_block,
)


def _sample_block() -> MitigationBlock:
    return MitigationBlock(
        block_id="mb-test",
        direction=MitigationBlockDirection.BULLISH,
        status=MitigationBlockStatus.FRESH,
        high=Decimal("2315"),
        low=Decimal("2309"),
        origin_bar_index=14,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        displacement_bar_index=15,
        displacement_time_utc=datetime(2026, 1, 1, 1, tzinfo=UTC),
        formation_bar_index=16,
        formation_time_utc=datetime(2026, 1, 1, 2, tzinfo=UTC),
        quality=MitigationBlockQuality.LOW,
        strength=Decimal("0"),
        is_confirmed=False,
        confirmation_reason="Awaiting price interaction",
        evidence=["Displacement magnitude 1.5"],
    )


def test_passes_minimum(mitigation_block_config) -> None:
    scorer = QualityScorer(mitigation_block_config)
    engine = MitigationBlockEngine(config=mitigation_block_config)
    candles = build_bullish_mitigation_base_candles()
    blocks = engine.detect_bullish_blocks(candles)

    assert blocks
    assert scorer.passes_minimum(blocks[0].strength)


def test_structure_alignment_scoring(mitigation_block_config) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    candles = build_bullish_mitigation_base_candles()
    structure = build_sample_structure()
    blocks = engine.detect_bullish_blocks(candles, structure)

    assert blocks
    assert blocks[0].structure_alignment is True


def test_liquidity_confluence_scoring(mitigation_block_config) -> None:
    scorer = QualityScorer(mitigation_block_config)
    block = _sample_block()
    liquidity = LiquidityState(
        active_zones=[
            LiquidityZone(
                zone_id="liq-1",
                side=LiquiditySide.BUY_SIDE,
                upper_bound=Decimal("2316"),
                lower_bound=Decimal("2308"),
                anchor_price=Decimal("2312"),
                cluster_size=3,
                timestamp_utc=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        ],
        bar_count=20,
    )

    scored = scorer.score(block, candles_count=20, liquidity_state=liquidity)
    assert scored.liquidity_confluence is True


def test_order_block_confluence_scoring(mitigation_block_config) -> None:
    scorer = QualityScorer(mitigation_block_config)
    candles = build_bullish_mitigation_base_candles()
    parent = parent_order_block_for_bullish_mitigation(candles)
    block = _sample_block()

    scored = scorer.score(block, candles_count=20, order_blocks=[parent])
    assert scored.order_block_confluence is True


def test_fvg_confluence_scoring(mitigation_block_config) -> None:
    scorer = QualityScorer(mitigation_block_config)
    block = _sample_block()
    fvg_state = FairValueGapState(
        active_gaps=[
            FairValueGap(
                gap_id="fvg-1",
                direction=FairValueGapDirection.BULLISH,
                status=FairValueGapStatus.OPEN,
                high=Decimal("2318"),
                low=Decimal("2307"),
                ce_price=Decimal("2312.5"),
                gap_size=Decimal("11"),
                gap_size_pips=Decimal("110"),
                origin_bar_index=14,
                origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
                candle_a_index=14,
                candle_b_index=15,
                candle_c_index=16,
                quality=FairValueGapQuality.HIGH,
                strength=Decimal("0.8"),
            ),
        ],
        bar_count=20,
    )

    scored = scorer.score(block, candles_count=20, fair_value_gap_state=fvg_state)
    assert scored.fvg_confluence is True


def test_htf_alignment_scoring(mitigation_block_config) -> None:
    scorer = QualityScorer(mitigation_block_config)
    block = _sample_block()
    htf = sample_htf_mitigation_block()

    scored = scorer.score(block, candles_count=20, htf_mitigation_blocks=[htf])
    assert scored.htf_aligned is True
    assert htf.block_id in scored.htf_block_ids


def test_premium_discount_classification(mitigation_block_config) -> None:
    scorer = QualityScorer(mitigation_block_config)
    block = _sample_block()
    structure = build_sample_structure()

    zone, range_high, range_low, _ = scorer.classify_premium_discount(block, structure)
    assert zone in PremiumDiscountZone
    assert range_high is not None
    assert range_low is not None


def test_classify_structure_scope(mitigation_block_config) -> None:
    scorer = QualityScorer(mitigation_block_config)
    block = _sample_block()
    structure = build_sample_structure()

    scope, score, evidence = scorer.classify_structure_scope(block, structure)
    assert scope in StructureScope
    assert score >= Decimal("0")
    assert evidence


def test_classify_nesting(mitigation_block_config) -> None:
    scorer = QualityScorer(mitigation_block_config)
    candles = build_bullish_mitigation_base_candles()
    parent = parent_order_block_for_bullish_mitigation(candles)
    block = _sample_block()

    nested, evidence = scorer.classify_nesting(block, order_blocks=[parent])
    assert nested.is_nested is True
    assert nested.parent_zone_id == parent.block_id
    assert evidence


def test_unconfirmed_strength_capped(mitigation_block_config) -> None:
    scorer = QualityScorer(mitigation_block_config)
    block = _sample_block().model_copy(update={"status": MitigationBlockStatus.FRESH})
    structure = build_sample_structure()
    liquidity = LiquidityState(
        active_zones=[
            LiquidityZone(
                zone_id="liq-1",
                side=LiquiditySide.BUY_SIDE,
                upper_bound=Decimal("2316"),
                lower_bound=Decimal("2308"),
                anchor_price=Decimal("2312"),
                cluster_size=3,
                timestamp_utc=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        ],
        bar_count=20,
    )

    scored = scorer.score(
        block,
        candles_count=20,
        structure=structure,
        liquidity_state=liquidity,
    )
    assert scored.strength <= Decimal("0.75")


def test_score_confluence_method(mitigation_block_config) -> None:
    engine = MitigationBlockEngine(config=mitigation_block_config)
    candles = build_bearish_mitigation_base_candles()
    blocks = engine.detect_bearish_blocks(candles)

    assert blocks
    enriched = engine.score_confluence(blocks[0], None, None, None, None)
    assert enriched.block_id == blocks[0].block_id
