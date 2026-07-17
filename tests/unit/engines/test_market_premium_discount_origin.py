"""Unit tests for dealing range origin and swing anchor selection."""

from decimal import Decimal

import pytest

pytest_plugins = ["tests.unit.engines.premium_discount_conftest"]

from backend.engines.market_premium_discount.origin import DealingRangeBuilder, SwingAnchorSelector
from backend.engines.market_premium_discount.schemas import DealingRangeScope
from backend.engines.market_structure.schemas import SwingKind, SwingLabel, SwingPoint, TrendDirection
from tests.unit.engines.premium_discount_conftest import (
    build_premium_discount_candles,
    build_premium_discount_structure,
    premium_config,
)


def test_select_anchors_latest_confirmed() -> None:
    config = premium_config(swing_selection_mode="latest_confirmed")
    selector = SwingAnchorSelector(config)
    structure = build_premium_discount_structure()
    candles = build_premium_discount_candles(30)

    high, low = selector.select_anchors(structure, DealingRangeScope.EXTERNAL, candles)

    assert high is not None
    assert low is not None
    assert high.kind is SwingKind.SWING_HIGH
    assert low.kind is SwingKind.SWING_LOW


def test_select_anchors_range_extreme() -> None:
    config = premium_config(swing_selection_mode="range_extreme")
    selector = SwingAnchorSelector(config)
    structure = build_premium_discount_structure()
    candles = build_premium_discount_candles(30)

    high, low = selector.select_anchors(structure, DealingRangeScope.EXTERNAL, candles)

    assert high.price == max(point.price for point in structure.swing_highs)
    assert low.price == min(point.price for point in structure.swing_lows)


def test_select_anchors_structure_state() -> None:
    config = premium_config(swing_selection_mode="structure_state")
    selector = SwingAnchorSelector(config)
    structure = build_premium_discount_structure()
    candles = build_premium_discount_candles(30)

    high, low = selector.select_anchors(structure, DealingRangeScope.EXTERNAL, candles)

    assert high.price == structure.external_structure.last_swing_high.price
    assert low.price == structure.external_structure.last_swing_low.price


def test_build_external_dealing_range() -> None:
    config = premium_config()
    builder = DealingRangeBuilder(config)
    structure = build_premium_discount_structure()
    candles = build_premium_discount_candles(30)

    dealing_range = builder.build(structure, DealingRangeScope.EXTERNAL, candles, timeframe="H1")

    assert dealing_range.is_valid is True
    assert dealing_range.high > dealing_range.low
    assert dealing_range.equilibrium == (dealing_range.high + dealing_range.low) / Decimal("2")
    assert dealing_range.scope is DealingRangeScope.EXTERNAL


def test_build_internal_dealing_range() -> None:
    config = premium_config()
    builder = DealingRangeBuilder(config)
    structure = build_premium_discount_structure()
    candles = build_premium_discount_candles(30)

    dealing_range = builder.build(structure, DealingRangeScope.INTERNAL, candles, timeframe="H1")

    assert dealing_range.is_valid is True
    assert dealing_range.scope is DealingRangeScope.INTERNAL
    assert dealing_range.range_size >= config.min_range_size_price


def test_missing_structure_returns_invalid_range() -> None:
    config = premium_config()
    builder = DealingRangeBuilder(config)
    candles = build_premium_discount_candles(30)

    dealing_range = builder.build(None, DealingRangeScope.EXTERNAL, candles, timeframe="H1")

    assert dealing_range.is_valid is False
    assert "Structure context unavailable" in dealing_range.invalidation_reason


def test_missing_swings_returns_invalid_range() -> None:
    config = premium_config()
    builder = DealingRangeBuilder(config)
    base = build_premium_discount_structure()
    structure = base.model_copy(
        update={
            "swing_highs": [],
            "swing_lows": [],
            "external_structure": base.external_structure.model_copy(
                update={"last_swing_high": None, "last_swing_low": None},
            ),
        },
    )
    candles = build_premium_discount_candles(30)

    dealing_range = builder.build(structure, DealingRangeScope.EXTERNAL, candles, timeframe="H1")

    assert dealing_range.is_valid is False
    assert "Missing swing anchors" in dealing_range.invalidation_reason


def test_range_size_below_minimum_invalidates() -> None:
    config = premium_config(min_range_size_pips=500.0)
    builder = DealingRangeBuilder(config)
    structure = build_premium_discount_structure()
    candles = build_premium_discount_candles(30)

    dealing_range = builder.build(structure, DealingRangeScope.INTERNAL, candles, timeframe="H1")

    assert dealing_range.is_valid is False
    assert "Range size below minimum" in dealing_range.invalidation_reason


def test_same_bar_range_rejected_when_disabled() -> None:
    config = premium_config(allow_same_bar_range=False, min_swing_quality_score=0.0)
    builder = DealingRangeBuilder(config)
    base = build_premium_discount_structure()
    same_bar = SwingPoint(
        price=Decimal("2350"),
        timestamp_utc=base.timestamp_utc,
        bar_index=8,
        kind=SwingKind.SWING_HIGH,
        label=SwingLabel.HH,
    )
    same_bar_low = same_bar.model_copy(update={"price": Decimal("2300"), "kind": SwingKind.SWING_LOW, "label": SwingLabel.LL})
    structure = base.model_copy(
        update={
            "swing_highs": [same_bar],
            "swing_lows": [same_bar_low],
            "external_structure": base.external_structure.model_copy(
                update={"last_swing_high": same_bar, "last_swing_low": same_bar_low},
            ),
        },
    )
    candles = build_premium_discount_candles(30)

    dealing_range = builder.build(structure, DealingRangeScope.EXTERNAL, candles, timeframe="H1")

    assert dealing_range.is_valid is False
    assert "same bar" in dealing_range.invalidation_reason.lower()


def test_swing_quality_scoring() -> None:
    selector = SwingAnchorSelector(premium_config())
    structure = build_premium_discount_structure()
    swing = structure.swing_highs[0]

    score = selector.score_swing_quality(swing, structure, bar_count=30)

    assert Decimal("0") <= score <= Decimal("1")
    assert score >= Decimal("0.5")
