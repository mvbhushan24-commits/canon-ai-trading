"""Unit tests for premium / discount quality scoring."""

from decimal import Decimal

pytest_plugins = ["tests.unit.engines.premium_discount_conftest"]

from backend.engines.market_premium_discount.quality import QualityScorer
from backend.engines.market_premium_discount.schemas import (
    FibDirection,
    InstitutionalZoneType,
    PremiumDiscountBias,
    PremiumDiscountQuality,
    PremiumDiscountZone,
)
from backend.engines.market_structure.schemas import TrendDirection
from tests.unit.engines.premium_discount_conftest import (
    build_premium_discount_structure,
    build_valid_dealing_range,
    discount_order_blocks,
    nested_order_blocks,
    premium_config,
    premium_order_blocks,
    sample_htf_premium_discount_context,
    sample_liquidity_state,
)


def test_score_range_updates_strength_and_quality() -> None:
    scorer = QualityScorer(premium_config())
    dealing_range = build_valid_dealing_range()
    structure = build_premium_discount_structure()

    scored = scorer.score_range(dealing_range, structure)

    assert scored.strength > Decimal("0")
    assert scored.quality in PremiumDiscountQuality


def test_score_analysis_returns_bias_and_confidence() -> None:
    config = premium_config()
    scorer = QualityScorer(config)
    dealing_range = build_valid_dealing_range()
    structure = build_premium_discount_structure()
    zone_entries = scorer.collect_zone_entries(
        order_blocks=discount_order_blocks(dealing_range),
        fair_value_gap_state=None,
        breaker_blocks=None,
        mitigation_blocks=None,
        liquidity_state=sample_liquidity_state(dealing_range),
        dealing_range=dealing_range,
    )

    strength, quality, bias, confidence = scorer.score_analysis(
        dealing_range=dealing_range,
        structure=structure,
        price_location=PremiumDiscountZone.DISCOUNT,
        current_price=dealing_range.low + Decimal("2"),
        liquidity_state=sample_liquidity_state(dealing_range),
        zone_entries=zone_entries,
        htf_context=sample_htf_premium_discount_context(dealing_range),
        mtf_premium=None,
        mtf_discount=None,
        bar_count=30,
    )

    assert Decimal("0") <= strength <= Decimal("1")
    assert quality in PremiumDiscountQuality
    assert bias is PremiumDiscountBias.DISCOUNT
    assert confidence > Decimal("0")


def test_score_analysis_undetermined_on_invalid_range() -> None:
    scorer = QualityScorer(premium_config())
    dealing_range = build_valid_dealing_range().model_copy(update={"is_valid": False})

    _, _, bias, confidence = scorer.score_analysis(
        dealing_range=dealing_range,
        structure=None,
        price_location=PremiumDiscountZone.EQUILIBRIUM,
        current_price=Decimal("2325"),
        liquidity_state=None,
        zone_entries=[],
        htf_context=None,
        mtf_premium=None,
        mtf_discount=None,
        bar_count=20,
    )

    assert bias is PremiumDiscountBias.UNDETERMINED
    assert confidence == Decimal("0")


def test_collect_zone_entries_from_order_blocks() -> None:
    scorer = QualityScorer(premium_config())
    dealing_range = build_valid_dealing_range()
    entries = scorer.collect_zone_entries(
        order_blocks=premium_order_blocks(dealing_range) + discount_order_blocks(dealing_range),
        fair_value_gap_state=None,
        breaker_blocks=None,
        mitigation_blocks=None,
        liquidity_state=None,
        dealing_range=dealing_range,
    )

    assert len(entries) == 4
    assert any(entry.zone_type is InstitutionalZoneType.ORDER_BLOCK for entry in entries)


def test_assemble_arrays_clusters_by_territory() -> None:
    config = premium_config(min_array_entries=2, array_cluster_pips=20.0)
    scorer = QualityScorer(config)
    dealing_range = build_valid_dealing_range()
    entries = scorer.collect_zone_entries(
        order_blocks=premium_order_blocks(dealing_range),
        fair_value_gap_state=None,
        breaker_blocks=None,
        mitigation_blocks=None,
        liquidity_state=None,
        dealing_range=dealing_range,
    )

    premium_arrays = scorer.assemble_arrays(entries, dealing_range, PremiumDiscountZone.PREMIUM)

    assert premium_arrays
    assert premium_arrays[0].territory is PremiumDiscountZone.PREMIUM
    assert premium_arrays[0].entry_count >= 2


def test_detect_nested_zones() -> None:
    config = premium_config(nesting_enabled=True, nest_overlap_min_percent=80.0)
    scorer = QualityScorer(config)
    dealing_range = build_valid_dealing_range()
    entries = scorer.collect_zone_entries(
        order_blocks=nested_order_blocks(dealing_range),
        fair_value_gap_state=None,
        breaker_blocks=None,
        mitigation_blocks=None,
        liquidity_state=None,
        dealing_range=dealing_range,
    )

    nested_premium, nested_discount = scorer.detect_nested_zones(entries, dealing_range)

    assert nested_premium or nested_discount


def test_detect_nested_zones_disabled() -> None:
    scorer = QualityScorer(premium_config(nesting_enabled=False))
    dealing_range = build_valid_dealing_range()
    entries = scorer.collect_zone_entries(
        order_blocks=nested_order_blocks(dealing_range),
        fair_value_gap_state=None,
        breaker_blocks=None,
        mitigation_blocks=None,
        liquidity_state=None,
        dealing_range=dealing_range,
    )

    nested_premium, nested_discount = scorer.detect_nested_zones(entries, dealing_range)

    assert nested_premium == []
    assert nested_discount == []


def test_mtf_premium_alignment() -> None:
    config = premium_config(mtf_alignment_min_score=0.3)
    scorer = QualityScorer(config)
    dealing_range = build_valid_dealing_range()
    htf_context = sample_htf_premium_discount_context(dealing_range).model_copy(
        update={"price_location": PremiumDiscountZone.PREMIUM},
    )
    entries = scorer.collect_zone_entries(
        order_blocks=premium_order_blocks(dealing_range),
        fair_value_gap_state=None,
        breaker_blocks=None,
        mitigation_blocks=None,
        liquidity_state=None,
        dealing_range=dealing_range,
    )
    arrays = scorer.assemble_arrays(entries, dealing_range, PremiumDiscountZone.PREMIUM)

    alignment = scorer.score_mtf_premium_alignment(
        ltf_timeframe="H1",
        ltf_range=dealing_range,
        ltf_location=PremiumDiscountZone.PREMIUM,
        ltf_arrays=arrays,
        htf_context=htf_context,
        structure=build_premium_discount_structure().model_copy(
            update={"current_trend": TrendDirection.BEARISH},
        ),
    )

    assert alignment is not None
    assert alignment.territory is PremiumDiscountZone.PREMIUM


def test_build_htf_contexts() -> None:
    scorer = QualityScorer(premium_config())
    htf_context = sample_htf_premium_discount_context().model_copy(
        update={"price_location": PremiumDiscountZone.EQUILIBRIUM},
    )

    htf_premium, htf_discount = scorer.build_htf_contexts(htf_context)

    assert htf_premium is not None
    assert htf_discount is not None


def test_resolve_fib_direction_from_trend() -> None:
    scorer = QualityScorer(premium_config(fibonacci_direction_mode="structure_trend"))
    structure = build_premium_discount_structure().model_copy(update={"current_trend": TrendDirection.BEARISH})

    assert scorer.resolve_fib_direction(structure) is FibDirection.BEARISH

    bullish_structure = structure.model_copy(update={"current_trend": TrendDirection.BULLISH})
    assert scorer.resolve_fib_direction(bullish_structure) is FibDirection.BULLISH


def test_missing_liquidity_uses_default_score() -> None:
    scorer = QualityScorer(premium_config())
    dealing_range = build_valid_dealing_range()

    score = scorer._liquidity_score(dealing_range, None)

    assert score == Decimal("0.3")
