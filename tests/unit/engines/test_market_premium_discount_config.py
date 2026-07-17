"""Unit tests for premium / discount configuration."""

from decimal import Decimal
from pathlib import Path

import pytest

from backend.engines.market_premium_discount.config import (
    PremiumDiscountConfig,
    PremiumDiscountQualityWeights,
    ZoneStatusFilters,
    load_market_premium_discount_config,
)


def test_load_market_premium_discount_config(tmp_path: Path) -> None:
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text(
        """
market_premium_discount:
  enabled: true
  timeframes:
    - H1
    - H4
  min_candles: 15
  lookback: 80
  pip_size: 0.1
  primary_range_mode: internal
  min_range_size_pips: 12.0
  max_range_age_bars: 150
  allow_same_bar_range: true
  invalidate_on_bos: false
  invalidate_on_choch: true
  swing_selection_mode: range_extreme
  swing_replacement_mode: confirmed_only
  equilibrium_tolerance_pips: 4.0
  price_reference: mid
  array_cluster_pips: 6.0
  min_array_entries: 2
  mtf_alignment_min_score: 0.55
  nest_overlap_min_percent: 85.0
  nesting_enabled: false
  fibonacci:
    enabled: true
    direction_mode: auto
    levels: [0.0, 0.382, 0.5, 0.618, 1.0]
  ote:
    enabled: true
    fib_low: 0.62
    fib_high: 0.79
    default_direction: bearish
    require_zone_overlap: true
    min_overlapping_zones: 2
  institutional:
    max_narrative_lines: 8
    include_htf_in_narrative: false
    include_ote_in_narrative: false
  min_quality_score: 0.5
  quality_weights:
    swing_quality: 0.20
    structure_quality: 0.15
    liquidity_confirmation: 0.10
    htf_alignment: 0.15
    fvg_alignment: 0.08
    order_block_alignment: 0.08
    breaker_alignment: 0.07
    mitigation_alignment: 0.07
    freshness: 0.05
    distance_from_equilibrium: 0.05
  zone_filters:
    order_block_statuses: [fresh]
    fvg_statuses: [open]
    breaker_statuses: [confirmed]
    mitigation_statuses: [fresh, confirmed]
engines:
  market_premium_discount: true
""",
        encoding="utf-8",
    )

    config = load_market_premium_discount_config(yaml_path=yaml_file)

    assert config.enabled is True
    assert config.timeframes == ["H1", "H4"]
    assert config.min_candles == 15
    assert config.primary_range_mode == "internal"
    assert config.swing_selection_mode == "range_extreme"
    assert config.price_reference == "mid"
    assert config.fibonacci_direction_mode == "auto"
    assert config.ote_default_direction == "bearish"
    assert config.ote_require_zone_overlap is True
    assert config.institutional_max_narrative_lines == 8
    assert config.min_quality_score == 0.5
    assert config.zone_filters.order_block_statuses == ["fresh"]


def test_quality_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="quality_weights must sum to 1.0"):
        PremiumDiscountQualityWeights(
            swing_quality=0.5,
            structure_quality=0.5,
            liquidity_confirmation=0.5,
            htf_alignment=0.5,
            fvg_alignment=0.5,
            order_block_alignment=0.5,
            breaker_alignment=0.5,
            mitigation_alignment=0.5,
            freshness=0.5,
            distance_from_equilibrium=0.5,
        )


def test_fibonacci_levels_require_equilibrium() -> None:
    with pytest.raises(ValueError, match="fibonacci.levels must include 0.5 equilibrium level"):
        PremiumDiscountConfig(fibonacci_levels=[0.0, 0.382, 0.618, 1.0])


def test_lookback_must_be_gte_min_candles() -> None:
    with pytest.raises(ValueError, match="lookback must be >= min_candles"):
        PremiumDiscountConfig(min_candles=30, lookback=20)


def test_primary_range_mode_validation() -> None:
    with pytest.raises(ValueError, match="primary_range_mode"):
        PremiumDiscountConfig(primary_range_mode="invalid")


def test_price_reference_validation() -> None:
    with pytest.raises(ValueError, match="price_reference"):
        PremiumDiscountConfig(price_reference="typical")


def test_ote_bounds_validation() -> None:
    with pytest.raises(ValueError, match="ote.fib_low must be less than ote.fib_high"):
        PremiumDiscountConfig(ote_fib_low=0.8, ote_fib_high=0.62)


def test_zone_filters_cannot_be_empty() -> None:
    with pytest.raises(ValueError, match="Zone status filter lists cannot be empty"):
        ZoneStatusFilters(order_block_statuses=[])


def test_config_property_accessors() -> None:
    config = PremiumDiscountConfig(
        equilibrium_tolerance_pips=3.0,
        pip_size=0.1,
        array_cluster_pips=8.0,
        min_range_size_pips=10.0,
    )
    assert config.equilibrium_tolerance_price == Decimal(str(3.0 * 0.1))
    assert config.array_cluster_price == Decimal(str(8.0 * 0.1))
    assert config.min_range_size_price == Decimal(str(10.0 * 0.1))


def test_score_values_must_be_unit_interval() -> None:
    with pytest.raises(ValueError, match="Score values must be between 0 and 1"):
        PremiumDiscountConfig(min_quality_score=1.5)


def test_percent_values_validation() -> None:
    with pytest.raises(ValueError, match="Percent values must be between 0 and 100"):
        PremiumDiscountConfig(nest_overlap_min_percent=150.0)


def test_timeframes_normalized_to_uppercase() -> None:
    config = PremiumDiscountConfig(timeframes=["h1", " m15 "])
    assert config.timeframes == ["H1", "M15"]


def test_defaults_when_yaml_section_missing(tmp_path: Path) -> None:
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text("engines: {}\n", encoding="utf-8")
    config = load_market_premium_discount_config(yaml_path=yaml_file)
    assert config.enabled is False
    assert config.timeframes == ["M15", "H1", "H4"]
